#!/usr/bin/env python3
"""Prove a generator rebuild still emits Phase-1 and ranks related scenes."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent


GROK_QC = "Approved · Grok Bot QC 5/5"
# Weather-rework scenes re-approved by Cosmo QC before the 2026-10-05 zero-out
# (approval_status Approved on main 7046a32). Frozen: new approvals use GROK_QC.
PRIOR_WEATHER_APPROVALS = frozenset(
    f"GR-01-{i:03d}" for i in (*range(1, 52), 53, 54, 55, 56, 59, 62, 63)
)


def grok_qc_approved(raw: dict) -> bool:
    """Approved by a Jason-authorized Grok Bot QC approval PR (2026-10-05 on)."""
    return raw.get("approval_status") == "Approved" and raw.get("qc_status") == GROK_QC


def load_builder():
    spec = importlib.util.spec_from_file_location("build_index", TOOLS / "build_index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    build = load_builder()
    tags = build.load_tags()
    scenes, meta, warnings = build.load_scenes(tags)
    if len(scenes) != 365:
        raise SystemExit(f"expected 365 scenes, got {len(scenes)}")
    if warnings:
        raise SystemExit("unexpected warnings:\n" + "\n".join(warnings))

    # Signed-off day/night matches the scenario-hour rule for every tagged scene.
    mismatches = []
    for scene in scenes:
        stored = tags[scene["entry_id"]]
        got = build.daynight(scene["scenario_label"])
        if got != stored["daynight"]:
            mismatches.append((scene["entry_id"], got, stored["daynight"]))
    if mismatches:
        raise SystemExit(f"day/night drift: {mismatches[:5]}")

    # Same region first, then shared moods, deterministic, four thumbs.
    rel = build.related_ids(meta, "GR-01-001")
    if len(rel) != 4:
        raise SystemExit(f"GR-01-001 related count {len(rel)}")
    regions = {meta[eid][0] for eid in rel}
    if regions != {"Attica"}:
        raise SystemExit(f"GR-01-001 related left Attica: {rel} {regions}")
    if rel != sorted(rel):
        # Same-region urban+historic peers tie on shared count (2) and sort by id.
        raise SystemExit(f"tiebreak not entry-id order: {rel}")
    again = build.related_ids(meta, "GR-01-001")
    if again != rel:
        raise SystemExit("related ranking is not stable")

    # A scene that only shares a mood, in another region, must not outrank Attica.
    outside = [eid for eid, row in meta.items() if row[0] != "Attica" and "historic" in row[2]]
    if not outside:
        raise SystemExit("fixture missing a non-Attica historic scene")
    if any(eid in rel for eid in outside):
        raise SystemExit("non-region scene outranked same-region peers")

    # Missing 16:9 master: no related thumb, and the scene record drops the path.
    broken = json.loads(json.dumps(meta))
    victim = rel[0]
    broken[victim][3] = ""
    reranked = build.related_ids(broken, "GR-01-001")
    if victim in reranked:
        raise SystemExit("missing master still used as a related thumb")
    if len(reranked) != 4:
        raise SystemExit("related row did not backfill after a missing master")

    if build.existing_master("library/world/Greece/no-such-master.png"):
        raise SystemExit("missing path was treated as a master")
    sample = scenes[0]["file_16x9"]
    if not build.existing_master(sample):
        raise SystemExit("existing master was rejected")

    # Daylight control paths: both masters, or neither. Manifest files stay untouched.
    day_ids = [scene["entry_id"] for scene in scenes if scene.get("file_16x9_day")]
    if day_ids != [
        "GR-01-001", "GR-01-002", "GR-01-003", "GR-01-004", "GR-01-005",
        "GR-01-006", "GR-01-007", "GR-01-009", "GR-01-010", "GR-01-011",
        "GR-01-012", "GR-01-013", "GR-01-014", "GR-01-015", "GR-01-016",
        "GR-01-017", "GR-01-018", "GR-01-019", "GR-01-020", "GR-01-021",
    ]:
        raise SystemExit(f"daylight pair set drifted: {day_ids}")
    for scene in scenes:
        has16 = bool(scene.get("file_16x9_day"))
        has45 = bool(scene.get("file_4x5_day"))
        if has16 != has45 and not scene.get("daylight_primary"):
            raise SystemExit(f"{scene['entry_id']} published a one-sided daylight pair")
        if has16:
            if not scene["file_16x9_day"].endswith(f"{scene['entry_id'].lower()}-daylight-16x9.png"):
                raise SystemExit(f"unexpected daylight path {scene['file_16x9_day']}")
            if not build.existing_master(scene["file_16x9_day"]) or not build.existing_master(scene["file_4x5_day"]):
                raise SystemExit(f"{scene['entry_id']} daylight path is not on disk")
    if build.paired_daylight({
        "file_16x9_day": "library/world/Greece/no-such-day-16x9.png",
        "file_4x5_day": scenes[0]["file_4x5"],
    }) != ("", ""):
        raise SystemExit("a missing daylight master still published a pair")
    if build.paired_daylight({"daylight_variant": {"files": {"16x9": scenes[0]["file_16x9"]}}}) != ("", ""):
        raise SystemExit("a 16:9-only daylight variant published a pair")

    # Netherlands gate: provenance must be exactly genuine-daylight, and the day 16:9 must exist.
    present = scenes[0]["file_16x9"]
    genuine_probe = {
        "daylight_variant": {"provenance": "genuine-daylight"},
        "file_16x9_day": present,
    }
    if not build.is_genuine_daylight(genuine_probe):
        raise SystemExit("genuine-daylight gate rejected an existing day 16:9")
    if build.is_genuine_daylight({
        "daylight_variant": {"provenance": "interim-ai"},
        "file_16x9_day": present,
    }):
        raise SystemExit("a non-genuine provenance passed the daylight gate")
    if build.is_genuine_daylight({
        "daylight_variant": {"provenance": "genuine-daylight"},
        "file_16x9_day": "library/world/Greece/no-such-day.png",
    }):
        raise SystemExit("a missing day 16:9 passed the daylight gate")
    raw001 = json.loads((ROOT / "manifests" / "GR-01-001.json").read_text(encoding="utf-8"))
    raw001["file_16x9_day"] = raw001["daylight_variant"]["files"]["16x9"]
    if build.is_genuine_daylight(raw001):
        raise SystemExit("derivative GR-01-001 was treated as genuine daylight")
    for scene in scenes:
        raw = json.loads((ROOT / "manifests" / f"{scene['entry_id']}.json").read_text(encoding="utf-8"))
        if "daylight_primary" in raw:
            raise SystemExit(f"{scene['entry_id']} wrote daylight_primary onto the manifest")
        for key in ("file_16x9", "file_4x5"):
            if scene.get(key) != raw.get(key):
                raise SystemExit(f"{scene['entry_id']} night master {key} changed")
        probe = dict(raw)
        resolved = scene.get("file_16x9_day") or build.daylight_rel(raw, "16x9")
        if resolved:
            probe["file_16x9_day"] = resolved
        qualifies = build.is_genuine_daylight(probe)
        if bool(scene.get("daylight_primary")) != qualifies:
            raise SystemExit(
                f"{scene['entry_id']} daylight_primary does not match the genuine-daylight gate"
            )
    for scene in scenes:
        raw = json.loads((ROOT / "manifests" / f"{scene['entry_id']}.json").read_text(encoding="utf-8"))
        if scene.get("approval_status") != raw.get("approval_status"):
            raise SystemExit(f"{scene['entry_id']} approval_status changed in the page record")

    html = build.render_html(scenes, meta)
    for token in ('id="f-daynight"', 'id="f-mood"', "function relatedFor", "Copy link", "phase1Enhance"):
        if token not in html:
            raise SystemExit(f"generated page missing {token}")

    # Identity that must survive a rebuild.
    for token in (
        "G-PDJ4WSS725",
        "Free · no credit needed",
        "Download 16:9",
        "Download 4:5",
        "fmt-tab",
        "className='lb'",
        "#0D5EAF",
        "getAttribute('data-src-45')",
        "getAttribute('data-src-16')",
        "Jason D’s Vision",
    ):
        if token not in html:
            raise SystemExit(f"identity marker missing: {token}")
    if "dataset.src45" in html or "dataset.src16" in html:
        raise SystemExit("dataset.src accessor returned")
    if html.count("G-PDJ4WSS725") != 2:
        raise SystemExit("GA4 id must appear only as the loader and the config")
    if "gr-01-001-daylight-16x9.png" not in html or "gr-01-001-daylight-4x5.png" not in html:
        raise SystemExit("GR-01-001 daylight masters were not published")
    if "gr-01-008-daylight" in html or "gr-01-022-daylight" in html:
        raise SystemExit("a scene without a daylight pair was given a daylight path")
    if 'class="home-link"' not in html or 'href="https://jdvision.org/"' not in html:
        raise SystemExit("home link was dropped from the gallery")
    if "night-tab" not in html or "daylight_primary" not in html:
        raise SystemExit("daylight-primary mechanism missing from the page")
    if '"daylight_primary": true' in html:
        raise SystemExit("a card was marked daylight-primary without a genuine master on this tree")
    if 'class="narrate"' in html or ".mp3" in html:
        raise SystemExit("Listen control rendered without an audio file")
    if ".flag-chip.flag-no{background:linear-gradient(to bottom,transparent 35%,#00205B" not in html:
        raise SystemExit("Norway flag chip is not the Spain offset cross")

    # A one-off index.html that has lost Phase-1 is replaced by the generator.
    index_path = ROOT / "index.html"
    clobbered = html.replace('id="f-daynight"', 'id="removed-daynight"').replace(
        "function relatedFor", "function removedRelated"
    ).replace("Copy link", "Removed link")
    index_path.write_text(clobbered, encoding="utf-8")
    subprocess.check_call([sys.executable, str(TOOLS / "build_index.py")], cwd=ROOT)
    restored = index_path.read_text(encoding="utf-8")
    if restored != html:
        raise SystemExit("generator output did not match render_html after a clobber")
    for token in ('id="f-daynight"', "function relatedFor", "Copy link", "Copied", "card.id = s.entry_id"):
        if token not in restored:
            raise SystemExit(f"regenerate dropped {token}")
    if 'id="removed-daynight"' in restored or "function removedRelated" in restored:
        raise SystemExit("regenerate kept a clobbered page")

    # Second run is byte-stable, including the image sitemap the generator writes.
    first = (ROOT / "index.html").read_bytes()
    sitemap_path = ROOT / "image-sitemap.xml"
    first_sitemap = sitemap_path.read_bytes()
    subprocess.check_call([sys.executable, str(TOOLS / "build_index.py")], cwd=ROOT)
    second = (ROOT / "index.html").read_bytes()
    second_sitemap = sitemap_path.read_bytes()
    if first != second:
        raise SystemExit("two generator runs diverged")
    if first_sitemap != second_sitemap:
        raise SystemExit("two image-sitemap runs diverged")
    page = first.decode("utf-8")
    if "function relatedFor" not in page or 'id="f-mood"' not in page:
        raise SystemExit("on-disk index.html lost Phase-1")

    # Syntax-check every inline script.
    node = "node"
    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", page, flags=re.S)
    code_blocks = [body for body in scripts if "function" in body or "const " in body]
    if len(code_blocks) < 3:
        raise SystemExit(f"expected gallery scripts, found {len(code_blocks)}")
    with tempfile.TemporaryDirectory() as tmp:
        for index, body in enumerate(code_blocks):
            path = Path(tmp) / f"part{index}.js"
            path.write_text(body, encoding="utf-8")
            proc = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
            if proc.returncode != 0:
                raise SystemExit(f"script {index} failed syntax check:\n{proc.stderr}")

    sitemap_mod = importlib.util.spec_from_file_location(
        "build_image_sitemap", TOOLS / "build_image_sitemap.py"
    )
    sitemap = importlib.util.module_from_spec(sitemap_mod)
    sitemap_mod.loader.exec_module(sitemap)
    entries, skipped, problems = sitemap.collect()
    if problems:
        raise SystemExit("image sitemap problems:\n" + "\n".join(problems))
    manifests = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "manifests").glob("GR-01-*.json"))
    }
    if "GR-01-340" not in skipped and not grok_qc_approved(manifests["GR-01-340"]):
        raise SystemExit("GR-01-340 was not skipped as a Candidate")
    ids = [entry["entry_id"] for entry in entries]
    if any(entry_id in ids for entry_id in skipped):
        raise SystemExit("a Candidate was written into the image sitemap")
    # 347 was the approved count before the weather rework. GR-01-001–087
    # went Candidate in that merge. A weather-rework scene may be Approved
    # again only by (a) a Cosmo QC re-approval already on main before the
    # 2026-10-05 QC zero-out (frozen list below, as on main 7046a32), or
    # (b) a Jason-authorized Grok Bot QC approval PR (#23, #24, #27 and later),
    # which sets qc_status exactly GROK_QC. Anything else is a self-approval.
    weather = [f"GR-01-{i:03d}" for i in range(1, 88)]
    for entry_id in weather:
        if entry_id in skipped:
            continue
        raw = manifests.get(entry_id) or {}
        if grok_qc_approved(raw):
            continue
        if entry_id in PRIOR_WEATHER_APPROVALS and str(raw.get("qc_status") or "").startswith("Approved · Cosmo QC 5/5"):
            continue
        raise SystemExit(f"a weather-rework scene was not left Candidate: {entry_id}")
    # The 260 approvals outside the weather rework are unchanged. Every other
    # Approved scene is a prior weather re-approval or carries GROK_QC.
    legacy = [eid for eid in ids if not grok_qc_approved(manifests.get(eid) or {}) and eid not in weather]
    if len(legacy) != 260:
        raise SystemExit(f"expected 260 legacy approved scenes, got {len(legacy)}")
    approved = sorted(eid for eid, raw in manifests.items() if raw.get("approval_status") == "Approved")
    if sorted(ids) != approved:
        raise SystemExit("image sitemap scenes do not match the Approved manifests")
    sample = next(entry for entry in entries if entry["entry_id"] == "GR-01-088")
    if sample["loc"] != "https://greece.jdvision.org/#GR-01-088":
        raise SystemExit(f"copy-link loc {sample['loc']}")
    formats = [image["format"] for image in sample["images"]]
    if formats != ["16:9", "4:5"]:
        raise SystemExit(f"GR-01-088 formats {formats}")
    image = sample["images"][0]
    if image["title"] != "Sanctuary of the Great Gods, Samothrace" or image["geo_location"] != "Samothrace, Greece":
        raise SystemExit(f"place fields {image['title']!r} {image['geo_location']!r}")
    if image["caption"] != "Sanctuary of the Great Gods, Samothrace":
        raise SystemExit("caption was not the scene caption")
    if " " in image["loc"]:
        raise SystemExit("image:loc left a space unencoded")
    spaced = next(entry for entry in entries if entry["entry_id"] == "GR-01-224")
    if "Porto%20Lagos" not in spaced["images"][0]["loc"]:
        raise SystemExit(f"space not encoded: {spaced['images'][0]['loc']}")
    for entry in entries:
        raw = manifests[entry["entry_id"]]
        for image in entry["images"]:
            if image["format"] == "9:16" and not (ROOT / str(raw.get("file_9x16") or "")).is_file():
                raise SystemExit(f"9:16 image emitted without a master on disk: {entry['entry_id']}")
    tree_problems = sitemap.validate_tree(sitemap_path.read_text(encoding="utf-8"), entries)
    if tree_problems:
        raise SystemExit("sitemap tree:\n" + "\n".join(tree_problems))
    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    if "Sitemap: https://greece.jdvision.org/sitemap.xml" not in robots:
        raise SystemExit("existing sitemap line was dropped")
    if "Sitemap: https://greece.jdvision.org/image-sitemap.xml" not in robots:
        raise SystemExit("image sitemap line missing from robots.txt")
    if "function sceneAlt" not in page or "sceneAlt(s.caption, s.city)" not in page:
        raise SystemExit("gallery alt is not {caption} — {site}, {City}")
    if "sceneAlt(m[4], '')" not in page:
        raise SystemExit("related thumb alt was not updated")

    print("proof: regenerate kept Phase-1")
    print("related GR-01-001:", ", ".join(rel))
    print("scenes", len(scenes), "thumbs", sum(1 for row in meta.values() if row[3]))
    print("two runs identical, inline scripts parse")


if __name__ == "__main__":
    main()
