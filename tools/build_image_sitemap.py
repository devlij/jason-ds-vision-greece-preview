#!/usr/bin/env python3
"""Write image-sitemap.xml from live scene manifests.

Approved scenes only. One url per copy-link anchor, and one image:image per
master that exists on disk among 16:9, 4:5, and 9:16. Re-run this (or
tools/build_index.py) after an approval change; the file is not hand-edited.
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SHELL = Path(__file__).resolve().parent / "gallery_shell.html"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
IMAGE_NS = "http://www.google.com/schemas/sitemap-image/1.1"

# Page order is the work-order order. A format is emitted only when that
# master file exists, so a missing 9:16 never becomes an image:loc.
FORMATS = (
    ("16:9", "file_16x9"),
    ("4:5", "file_4x5"),
    ("9:16", "file_9x16"),
)

CANON_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]+)"')


def canonical_origin() -> str:
    """Absolute origin from the gallery canonical link, with a trailing slash."""
    shell = SHELL.read_text(encoding="utf-8")
    match = CANON_RE.search(shell)
    if not match:
        raise SystemExit("gallery shell has no canonical link")
    origin = match.group(1).strip()
    if not origin.startswith("https://"):
        raise SystemExit(f"canonical URL is not absolute https: {origin}")
    if not origin.endswith("/"):
        origin += "/"
    return origin


def master_exists(rel: str) -> bool:
    if not rel or not isinstance(rel, str):
        return False
    path = (ROOT / rel).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        return False
    return path.is_file()


def split_place(caption: str, city: str) -> tuple[str, str]:
    """Site name and city. Caption is '{site}, {City}' when the manifest is well formed."""
    caption = caption or ""
    city = city or ""
    suffix = ", " + city
    if city and caption.endswith(suffix):
        return caption[: -len(suffix)], city
    cut = caption.rfind(", ")
    if cut >= 0:
        site = caption[:cut]
        derived = caption[cut + 2 :]
        return site, city or derived
    return caption, city


def place_title(site: str, city: str) -> str:
    return f"{site}, {city}"


def place_alt(caption: str, site: str, city: str) -> str:
    return f"{caption} — {site}, {city}"


def geo_location(city: str, country: str) -> str:
    return f"{city}, {country}"


def xml_text(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def absolute_asset(origin: str, rel: str) -> str:
    encoded = "/".join(quote(segment, safe="") for segment in rel.split("/"))
    return origin + encoded


def page_loc(origin: str, entry_id: str) -> str:
    """Copy-link anchor on the canonical gallery: origin + '#' + entry id."""
    return origin + "#" + entry_id


def load_manifests() -> list[dict]:
    manifests = sorted((ROOT / "manifests").glob("GR-*.json"))
    if not manifests:
        raise SystemExit("no manifests/GR-*.json files")
    scenes = []
    for path in manifests:
        raw = json.loads(path.read_text(encoding="utf-8"))
        entry_id = raw.get("entry_id") or ""
        if not entry_id:
            raise SystemExit(f"{path.name} has no entry_id")
        raw["_path"] = path.name
        scenes.append(raw)
    scenes.sort(key=lambda item: item["entry_id"])
    return scenes


def collect(scenes: list[dict] | None = None) -> tuple[list[dict], list[str], list[str]]:
    """Approved scenes with the masters that exist right now.

    Returns (entries, skipped candidate ids, problems). Approval is read from
    each manifest at call time.
    """
    origin = canonical_origin()
    if scenes is None:
        scenes = load_manifests()
    entries: list[dict] = []
    skipped: list[str] = []
    problems: list[str] = []
    for raw in scenes:
        entry_id = raw["entry_id"]
        status = raw.get("approval_status") or "Candidate"
        if status != "Approved":
            skipped.append(entry_id)
            continue
        caption = str(raw.get("caption") or "")
        city = str(raw.get("city") or "")
        country = str(raw.get("country") or "")
        site, place_city = split_place(caption, city)
        title = place_title(site, place_city)
        if caption != title:
            problems.append(
                f"{entry_id} caption {caption!r} is not site, City ({title!r})"
            )
        if not city or not country:
            problems.append(f"{entry_id} missing city or country")
        images = []
        for label, key in FORMATS:
            rel = str(raw.get(key) or "")
            if not master_exists(rel):
                continue
            images.append(
                {
                    "format": label,
                    "loc": absolute_asset(origin, rel),
                    "caption": caption,
                    "title": title,
                    "geo_location": geo_location(place_city, country),
                }
            )
        if not images:
            problems.append(f"{entry_id} Approved but no 16:9, 4:5, or 9:16 master on disk")
            continue
        entries.append(
            {
                "entry_id": entry_id,
                "loc": page_loc(origin, entry_id),
                "images": images,
            }
        )
    return entries, skipped, problems


def render_xml(entries: list[dict]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!-- Generated by tools/build_image_sitemap.py from manifests. Approved scenes only. -->",
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ]
    for entry in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{xml_text(entry['loc'])}</loc>")
        for image in entry["images"]:
            lines.append("    <image:image>")
            lines.append(f"      <image:loc>{xml_text(image['loc'])}</image:loc>")
            lines.append(f"      <image:caption>{xml_text(image['caption'])}</image:caption>")
            lines.append(f"      <image:title>{xml_text(image['title'])}</image:title>")
            lines.append(
                f"      <image:geo_location>{xml_text(image['geo_location'])}</image:geo_location>"
            )
            lines.append("    </image:image>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")
    return "\n".join(lines)


def ensure_robots(text: str, image_sitemap_url: str) -> str:
    """Keep every existing line. Add the image sitemap if it is not already declared."""
    line = f"Sitemap: {image_sitemap_url}"
    body = text.replace("\r\n", "\n")
    existing = [item.strip() for item in body.splitlines()]
    if line in existing:
        if body.endswith("\n") or body == "":
            return body
        return body + "\n"
    if body and not body.endswith("\n"):
        body += "\n"
    return body + line + "\n"


def write_outputs() -> dict:
    origin = canonical_origin()
    entries, skipped, problems = collect()
    xml = render_xml(entries)
    # Round-trip so a bad escape cannot ship.
    ET.fromstring(xml)
    out = ROOT / "image-sitemap.xml"
    out.write_text(xml, encoding="utf-8")
    robots_path = ROOT / "robots.txt"
    previous = robots_path.read_text(encoding="utf-8") if robots_path.is_file() else ""
    image_url = origin + "image-sitemap.xml"
    updated = ensure_robots(previous, image_url)
    if "Sitemap: " + origin + "sitemap.xml" not in updated and "Sitemap: " + origin.rstrip("/") + "/sitemap.xml" not in updated:
        problems.append("robots.txt lost the existing sitemap.xml line")
    robots_path.write_text(updated, encoding="utf-8")
    counts = {"16:9": 0, "4:5": 0, "9:16": 0}
    for entry in entries:
        for image in entry["images"]:
            counts[image["format"]] += 1
    return {
        "scenes": len(entries),
        "images": sum(counts.values()),
        "formats": counts,
        "skipped_candidates": skipped,
        "problems": problems,
        "origin": origin,
    }


def validate_tree(xml: str, entries: list[dict]) -> list[str]:
    """Structural checks against the generated document and the live Approved set."""
    problems: list[str] = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        return [f"XML parse error: {exc}"]
    if root.tag != f"{{{SITEMAP_NS}}}urlset":
        problems.append(f"root tag {root.tag}")
    urls = list(root)
    if len(urls) != len(entries):
        problems.append(f"url count {len(urls)} != approved entries {len(entries)}")
    for node, entry in zip(urls, entries):
        loc = node.find(f"{{{SITEMAP_NS}}}loc")
        if loc is None or (loc.text or "") != entry["loc"]:
            problems.append(f"loc mismatch for {entry['entry_id']}")
        images = list(node.findall(f"{{{IMAGE_NS}}}image"))
        if len(images) != len(entry["images"]):
            problems.append(f"{entry['entry_id']} image count mismatch")
            continue
        for image_node, image in zip(images, entry["images"]):
            for child, key in (
                ("loc", "loc"),
                ("caption", "caption"),
                ("title", "title"),
                ("geo_location", "geo_location"),
            ):
                found = image_node.find(f"{{{IMAGE_NS}}}{child}")
                got = found.text if found is not None and found.text else ""
                if got != image[key]:
                    problems.append(f"{entry['entry_id']} {child} {got!r} != {image[key]!r}")
                if key == "loc" and not got.startswith("https://"):
                    problems.append(f"{entry['entry_id']} image:loc is not absolute https")
    return problems


def check_image_locs(xml: str, workers: int = 16) -> list[str]:
    """HEAD every image:loc. A pass is HTTP 200 without a redirect."""
    import concurrent.futures
    import urllib.error
    import urllib.request
    from urllib.request import Request

    root = ET.fromstring(xml)
    locs = []
    for image in root.findall(f".//{{{IMAGE_NS}}}image/{{{IMAGE_NS}}}loc"):
        if image.text:
            locs.append(image.text)
    if not locs:
        return ["no image:loc values to check"]

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)

    def head(url: str) -> tuple[str, int | str]:
        request = Request(url, method="HEAD", headers={"User-Agent": "jdvision-image-sitemap-check"})
        try:
            with opener.open(request, timeout=30) as response:
                return url, getattr(response, "status", response.getcode())
        except urllib.error.HTTPError as exc:
            return url, exc.code
        except Exception as exc:  # noqa: BLE001 — report the failure, do not invent a status
            return url, f"{type(exc).__name__}: {exc}"

    failures: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for url, status in pool.map(head, locs):
            if status != 200:
                failures.append(f"{status} {url}")
    return failures


def main() -> None:
    check_urls = "--check-urls" in sys.argv
    stats = write_outputs()
    xml = (ROOT / "image-sitemap.xml").read_text(encoding="utf-8")
    entries, _skipped, problems = collect()
    problems = list(dict.fromkeys(problems + stats["problems"] + validate_tree(xml, entries)))
    counts = stats["formats"]
    print(
        f"wrote image-sitemap.xml with {stats['scenes']} approved scenes, "
        f"{stats['images']} images "
        f"(16:9={counts['16:9']} 4:5={counts['4:5']} 9:16={counts['9:16']})"
    )
    print(f"skipped {len(stats['skipped_candidates'])} candidates")
    if check_urls:
        failures = check_image_locs(xml)
        if failures:
            problems.extend(failures[:20])
            problems.append(f"{len(failures)} image:loc responses were not HTTP 200")
        else:
            print(f"image:loc HTTP 200 for {stats['images']} urls")
    for problem in problems:
        print("problem:", problem, file=sys.stderr)
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
