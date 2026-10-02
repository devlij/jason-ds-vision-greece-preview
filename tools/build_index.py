#!/usr/bin/env python3
"""Write index.html from manifests and the Phase-1 gallery shell.

The published page is this script's output. Phase-1 (search, region, day/night,
mood, live count, clear-all, four related thumbnails, copy link, entry-id
anchors) lives in tools/gallery_shell.html. Re-running this script keeps those
controls. It does not rewrite master images.

A format tab, download, daylight control, or related thumbnail is emitted only
when that master file is on disk. The same run rewrites image-sitemap.xml from
the live approval status on each manifest.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL = Path(__file__).resolve().parent / "gallery_shell.html"
TAGS = Path(__file__).resolve().parent / "phase1_tags.json"

PUBLIC_KEYS = (
    "entry_id",
    "country",
    "region",
    "city",
    "caption",
    "scenario_label",
    "composition",
    "description",
    "alt_text",
    "file_16x9",
    "file_4x5",
    "license_badge",
    "license_anchor",
    "approval_status",
)

# Optional masters. Included only when the file exists, so the page never
# points a control at a missing image. Daylight is a pair: both files or neither.
OPTIONAL_FILES = (
    ("file_9x16", "file_9x16"),
    ("file_9x16_day", "file_9x16_day"),
)

HOUR_RE = re.compile(r"(\d{1,2}):(\d{2})")

# Fallback for a scene that is not yet in phase1_tags.json. Signed-off tags
# in that file win. Order is the filter order: Coastal, Mountain, Urban, Historic.
MOOD_RULES = (
    ("coastal", re.compile(
        r"\b(harbor|harbour|beach|bay|waterfront|coast|cape|marina|lagoon|lighthouse|sea|gulf)\b",
        re.I,
    )),
    ("mountain", re.compile(
        r"\b(mountain|gorge|summit|waterfall|highland|slope|massif|cave)\b",
        re.I,
    )),
    ("urban", re.compile(
        r"\b(square|street|old town|market|town hall|avenue|quarter|lane)\b",
        re.I,
    )),
    ("historic", re.compile(
        r"\b(temple|castle|monastery|ancient|palace|theatre|theater|fortress|monument|acropolis|ruins|sanctuary|cathedral|mosque)\b",
        re.I,
    )),
)

PHASE1_MARKERS = (
    'id="q"',
    'id="region"',
    'id="f-daynight"',
    'id="f-mood"',
    'id="result-count"',
    'id="clear"',
    "function relatedFor",
    "Copy link",
    "Copied",
    "card.id = s.entry_id",
    "phase1Enhance",
    "G-PDJ4WSS725",
    'class="badge"',
    "Download 16:9",
    "Download 4:5",
    "fmt-tab",
    "motion-tab",
    "className='lb'",
    "#0D5EAF",
    "getAttribute('data-src-45')",
    "getAttribute('data-src-16')",
)


def master_exists(rel: str) -> bool:
    if not rel or not isinstance(rel, str):
        return False
    path = (ROOT / rel).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        return False
    return path.is_file()


def existing_master(rel: str) -> str:
    return rel if master_exists(rel) else ""


def motion_files(entry_id: str, file_16x9: str) -> tuple[str, str]:
    """360° clip and poster, or empty strings when the file is not on disk.

    The button is published only for a scene whose mp4 is actually present.
    Pack 1 clips are not in this tree, so those scenes stay unwired here.
    """
    if not entry_id or not file_16x9:
        return "", ""
    folder = Path(file_16x9).parent.as_posix()
    slug = entry_id.lower()
    motion = existing_master(f"{folder}/{slug}-motion-10s-4x5.mp4")
    poster = existing_master(f"{folder}/{slug}-motion-10s-4x5-poster.jpg")
    return motion, poster


def paired_daylight(raw: dict) -> tuple[str, str]:
    """16:9 and 4:5 daylight masters, or neither.

    An explicit file_16x9_day / file_4x5_day pair wins. Otherwise the paths
    already recorded under daylight_variant.files are used. A control is
    published only when both files are on disk.
    """
    explicit16 = str(raw.get("file_16x9_day") or "")
    explicit45 = str(raw.get("file_4x5_day") or "")
    if explicit16 or explicit45:
        day16 = existing_master(explicit16)
        day45 = existing_master(explicit45)
    else:
        variant = raw.get("daylight_variant")
        files = variant.get("files") if isinstance(variant, dict) else None
        if not isinstance(files, dict):
            return "", ""
        day16 = existing_master(str(files.get("16x9") or ""))
        day45 = existing_master(str(files.get("4x5") or ""))
    if day16 and day45:
        return day16, day45
    return "", ""


def daynight(label: str) -> str:
    """Scenario hour. 07:00–18:59 is day; every other hour is night.

    This matches the signed-off Greece map (night at 03, 05, 06; day from 07).
    """
    match = HOUR_RE.search(label or "")
    if not match:
        return ""
    hour = int(match.group(1))
    if hour > 23:
        return ""
    return "day" if 7 <= hour <= 18 else "night"


def infer_mood(scene: dict) -> str:
    text = " ".join(
        str(scene.get(key) or "")
        for key in ("caption", "composition", "description", "city")
    )
    tags = [name for name, pattern in MOOD_RULES if pattern.search(text)]
    return ",".join(tags)


def load_tags() -> dict:
    if not TAGS.is_file():
        return {}
    data = json.loads(TAGS.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{TAGS} must be an object")
    return data


def load_scenes(tags: dict) -> tuple[list[dict], dict, list[str]]:
    manifests = sorted((ROOT / "manifests").glob("GR-*.json"))
    if not manifests:
        raise SystemExit("no manifests/GR-*.json files")
    scenes: list[dict] = []
    meta: dict[str, list] = {}
    warnings: list[str] = []
    for path in manifests:
        raw = json.loads(path.read_text(encoding="utf-8"))
        entry_id = raw.get("entry_id") or ""
        if not entry_id:
            raise SystemExit(f"{path.name} has no entry_id")
        scene = {key: raw[key] for key in PUBLIC_KEYS if key in raw}
        scene.setdefault("approval_status", "Candidate")
        scene.setdefault("license_badge", "Free · no credit needed")
        scene.setdefault("license_anchor", "#license")
        for key in ("file_16x9", "file_4x5"):
            rel = existing_master(str(raw.get(key) or ""))
            if rel:
                scene[key] = rel
            else:
                scene.pop(key, None)
                warnings.append(f"{entry_id} missing {key}")
        for src_key, dest_key in OPTIONAL_FILES:
            rel = existing_master(str(raw.get(src_key) or ""))
            if rel:
                scene[dest_key] = rel
        # Daylight is a pair: both masters on disk, or no control. The shell
        # also refuses to draw the button unless both paths are present.
        day16, day45 = paired_daylight(raw)
        if day16 and day45:
            scene["file_16x9_day"] = day16
            scene["file_4x5_day"] = day45
        motion, poster = motion_files(entry_id, scene.get("file_16x9") or str(raw.get("file_16x9") or ""))
        if motion:
            scene["file_motion_10s_4x5"] = motion
        if poster:
            scene["file_motion_poster"] = poster
        scenes.append(scene)

        stored = tags.get(entry_id) or {}
        computed = daynight(str(scene.get("scenario_label") or ""))
        if stored:
            mood = str(stored.get("mood") or "")
            signed = str(stored.get("daynight") or "")
            if signed and signed != computed:
                raise SystemExit(
                    f"{entry_id} day/night is {computed!r} from the scenario label, "
                    f"but tools/phase1_tags.json says {signed!r}. Update the tag file "
                    "if the scenario hour change is intentional."
                )
        else:
            mood = infer_mood(scene)
            warnings.append(f"{entry_id} has no signed-off mood tag; inferred {mood!r}")
        thumb = scene.get("file_16x9") or ""
        meta[entry_id] = [
            scene.get("region") or "",
            computed,
            mood,
            thumb,
            scene.get("caption") or "",
        ]
    scenes.sort(key=lambda item: item["entry_id"])
    ordered_meta = {scene["entry_id"]: meta[scene["entry_id"]] for scene in scenes}
    return scenes, ordered_meta, warnings


def related_ids(meta: dict, entry_id: str, limit: int = 4) -> list[str]:
    """Same region first, then shared mood count, then entry id. Top 4.

    Scenes with no 16:9 master are skipped so a related thumbnail is never
    rendered for a missing file.
    """
    me = meta.get(entry_id)
    if not me:
        return []
    mine = [tag for tag in (me[2] or "").split(",") if tag]
    scored: list[tuple] = []
    for oid, other in meta.items():
        if oid == entry_id or not other[3]:
            continue
        tags = [tag for tag in (other[2] or "").split(",") if tag]
        shared = sum(1 for tag in mine if tag in tags)
        if other[0] == me[0] or shared > 0:
            scored.append((0 if other[0] == me[0] else 1, -shared, oid))
    scored.sort()
    return [oid for _, _, oid in scored[:limit]]


def render_html(scenes: list[dict], meta: dict) -> str:
    shell = SHELL.read_text(encoding="utf-8")
    if shell.count("__SCENES__") != 1 or shell.count("__GREECE_META__") != 1:
        raise SystemExit("gallery shell must contain each placeholder once")
    scenes_json = json.dumps(scenes, ensure_ascii=False, indent=2)
    meta_json = json.dumps(meta, ensure_ascii=False, separators=(", ", ": "))
    html = shell.replace("__SCENES__", scenes_json).replace("__GREECE_META__", meta_json)
    if "__SCENES__" in html or "__GREECE_META__" in html:
        raise SystemExit("placeholder left in index.html")
    if "dataset.src45" in html or "dataset.src16" in html:
        raise SystemExit("refusing dataset.src accessors")
    missing = [marker for marker in PHASE1_MARKERS if marker not in html]
    if missing:
        raise SystemExit("regenerated index.html dropped Phase-1 markers: " + ", ".join(missing))
    # Missing-master guards must stay in the generator shell.
    for guard in ("if (!o[3]) continue;", "if (!m || !m[3]) return;", "file16 ?"):
        if guard not in html:
            raise SystemExit(f"missing-master guard not in generated page: {guard}")
    return html


def main() -> None:
    tags = load_tags()
    scenes, meta, warnings = load_scenes(tags)
    html = render_html(scenes, meta)
    out = ROOT / "index.html"
    out.write_text(html, encoding="utf-8")
    thumbs = sum(1 for row in meta.values() if row[3])
    print(f"wrote index.html with {len(scenes)} scenes, {thumbs} related thumbs")
    print("phase1: search+region, day/night, mood, result-count, clear-all, related, copy-link, deep-link")
    for warning in warnings:
        print("warn:", warning, file=sys.stderr)
    # Import lazily so loading this module does not cycle through the sitemap writer.
    import build_image_sitemap

    sitemap = build_image_sitemap.write_outputs()
    counts = sitemap["formats"]
    print(
        f"wrote image-sitemap.xml with {sitemap['scenes']} approved scenes, "
        f"{sitemap['images']} images "
        f"(16:9={counts['16:9']} 4:5={counts['4:5']} 9:16={counts['9:16']})"
    )
    if sitemap["problems"]:
        for problem in sitemap["problems"]:
            print("warn:", problem, file=sys.stderr)


if __name__ == "__main__":
    main()
