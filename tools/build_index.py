#!/usr/bin/env python3
"""Write index.html from manifests and the Phase-1 gallery shell.

The published page is this script's output. Phase-1 (search, region, day/night,
mood, live count, clear-all, four related thumbnails, copy link, entry-id
anchors) lives in tools/gallery_shell.html. Re-running this script keeps those
controls. It does not rewrite master images.

A format tab, download, daylight control, or related thumbnail is emitted only
when that master file is on disk. The same run rewrites image-sitemap.xml from
the live approval status on each manifest.

Genuine daylight is the card default only when ``daylight_variant.provenance``
is exactly ``genuine-daylight`` and the day 16:9 master exists. Night masters
stay on ``file_16x9``, ``file_4x5``, and ``file_9x16``. Derivative daylight
keeps the night card and the sun toggle. The flag is computed for the page
and is not written back onto the manifest.

A Night button is emitted only for a format whose night master is already
recorded and on disk. ``daylight_variant.source_night`` is the file-level
record. Scenes without that block still qualify when ``weather.is_day`` is 0
and the manifest's own lighting label is Night (the Greece equivalent of
Sweden's ``daynight: night``). Dawn, pre-dawn, and daylight plates do not.
Scenario hour is not a night-master record. A missing 9:16 is left empty and
is never filled from 16:9 or 4:5.
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
    "className='lb'",
    "#0D5EAF",
    "getAttribute('data-src-45')",
    "getAttribute('data-src-16')",
    "night-tab",
    "daylight_primary",
    "const GREECE_NIGHT=",
    "data-src-16-night",
    "data-src-916-night",
    "data-dl-night",
    "closest('.night-tab')",
    "closest('.pc-tab, .motion-tab, .gday-tab')",
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


def daylight_rel(raw: dict, key: str) -> str:
    """One daylight master path, if that file is already on disk.

    Explicit ``file_*_day`` wins. Otherwise the path recorded under
    ``daylight_variant.files`` is used. This does not require the 16:9/4:5 pair.
    """
    explicit_key = {"16x9": "file_16x9_day", "4x5": "file_4x5_day", "9x16": "file_9x16_day"}[key]
    explicit = existing_master(str(raw.get(explicit_key) or ""))
    if explicit:
        return explicit
    variant = raw.get("daylight_variant")
    files = variant.get("files") if isinstance(variant, dict) else None
    if not isinstance(files, dict):
        return ""
    return existing_master(str(files.get(key) or ""))


def is_genuine_daylight(scene: dict) -> bool:
    """True only when provenance is exactly genuine-daylight and the day 16:9 exists.

    Derivative daylight (a relight of the night master, no ``provenance`` of
    ``genuine-daylight``) does not qualify. The flag is computed for the page
    payload and is not written back onto the manifest.
    """
    variant = scene.get("daylight_variant")
    if not isinstance(variant, dict) or variant.get("provenance") != "genuine-daylight":
        return False
    return master_exists(scene.get("file_16x9_day"))


def lighting_label(raw: dict) -> str:
    """Final lighting segment of qc_status. Read-only. Not written back."""
    status = str(raw.get("qc_status") or "").strip()
    if not status:
        return ""
    return status.split("·")[-1].strip()


def load_night_masters() -> dict[str, list[str]]:
    """Night-master URLs keyed by entry id: [16:9, 4:5, 9:16].

    A slot is filled only when that format's own master is on disk and the
    manifest records it as the night plate:

    - ``daylight_variant.source_night`` names that exact path, or
    - ``weather.is_day`` is 0 and the lighting label is exactly ``Night``.

    An empty slot means that format has no night master. Another format is
    never copied in, so a missing 9:16 stays missing. Scenario hour is ignored.
    """
    found: dict[str, list[str]] = {}
    keys = (("16x9", "file_16x9"), ("4x5", "file_4x5"), ("9x16", "file_9x16"))
    manifest_dir = ROOT / "manifests"
    for path in sorted(manifest_dir.glob("GR-*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            continue
        entry_id = str(raw.get("entry_id") or "")
        if not entry_id:
            continue
        variant = raw.get("daylight_variant")
        source = variant.get("source_night") if isinstance(variant, dict) else None
        if not isinstance(source, dict):
            source = {}
        weather = raw.get("weather")
        scene_night = (
            isinstance(weather, dict)
            and weather.get("is_day") == 0
            and lighting_label(raw) == "Night"
        )
        if not scene_night and not source:
            continue
        urls = ["", "", ""]
        for index, (fmt, key) in enumerate(keys):
            scene_rel = str(raw.get(key) or "").split("?", 1)[0].strip()
            info = source.get(fmt)
            recorded = ""
            if isinstance(info, dict):
                recorded = str(info.get("path") or "").split("?", 1)[0].strip()
            if recorded and recorded == scene_rel and master_exists(recorded):
                urls[index] = scene_rel
                continue
            if scene_night and scene_rel and master_exists(scene_rel):
                urls[index] = scene_rel
        if any(urls):
            found[entry_id] = urls
    return found


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
        # The sun toggle still requires the 16:9 and 4:5 pair. The genuine-daylight
        # gate is separate: provenance plus the day 16:9 file, even if 4:5 is absent.
        day16, day45 = paired_daylight(raw)
        if day16 and day45:
            scene["file_16x9_day"] = day16
            scene["file_4x5_day"] = day45
        resolved16 = day16 or daylight_rel(raw, "16x9")
        probe = dict(raw)
        if resolved16:
            probe["file_16x9_day"] = resolved16
        # Never trust a stale flag. Recompute from provenance + the day 16:9 file.
        if is_genuine_daylight(probe):
            scene["daylight_primary"] = True
            scene["file_16x9_day"] = resolved16
            resolved45 = day45 or daylight_rel(raw, "4x5")
            if resolved45:
                scene["file_4x5_day"] = resolved45
            resolved916 = daylight_rel(raw, "9x16")
            if resolved916:
                scene["file_9x16_day"] = resolved916
            variant = raw.get("daylight_variant")
            if isinstance(variant, dict):
                published: dict[str, str] = {}
                provenance = variant.get("provenance")
                if isinstance(provenance, str) and provenance:
                    published["provenance"] = provenance
                label = variant.get("scenario_label")
                if isinstance(label, str) and label:
                    published["scenario_label"] = label
                if published:
                    scene["daylight_variant"] = published
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
        # Related thumbnails follow the card default. Genuine daylight uses the
        # daylight 16:9; every other card keeps the original master.
        thumb = (
            scene["file_16x9_day"]
            if scene.get("daylight_primary") and scene.get("file_16x9_day")
            else scene.get("file_16x9") or ""
        )
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
    if (
        shell.count("__SCENES__") != 1
        or shell.count("__GREECE_META__") != 1
        or shell.count("__GREECE_NIGHT__") != 1
    ):
        raise SystemExit("gallery shell must contain each placeholder once")
    scenes_json = json.dumps(scenes, ensure_ascii=False, indent=2)
    meta_json = json.dumps(meta, ensure_ascii=False, separators=(", ", ": "))
    night = load_night_masters()
    night_json = json.dumps(night, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    html = (
        shell.replace("__SCENES__", scenes_json)
        .replace("__GREECE_META__", meta_json)
        .replace("__GREECE_NIGHT__", night_json)
    )
    if "__SCENES__" in html or "__GREECE_META__" in html or "__GREECE_NIGHT__" in html:
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
    assert_daylight_law(scenes, html)
    assert_night_law(night, html)
    return html


def assert_daylight_law(scenes: list[dict], html: str) -> None:
    """Greece uses the Netherlands genuine-daylight gate. Does not approve anything."""
    genuine = [scene for scene in scenes if scene.get("daylight_primary") is True]
    if html.count('"daylight_primary": true') != len(genuine):
        raise SystemExit("daylight_primary flags in the page do not match the payload")
    if "night-tab" not in html:
        raise SystemExit("gallery page is missing the nighttime toggle")
    for scene in scenes:
        entry_id = scene.get("entry_id") or ""
        raw_path = ROOT / "manifests" / f"{entry_id}.json"
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        if "daylight_primary" in raw:
            raise SystemExit(f"{entry_id} daylight_primary was written onto the manifest")
        if scene.get("approval_status") != raw.get("approval_status"):
            raise SystemExit(f"{entry_id} approval_status changed in the page record")
        for key in ("file_16x9", "file_4x5", "file_9x16"):
            raw_rel = str(raw.get(key) or "")
            page_rel = str(scene.get(key) or "")
            if raw_rel and page_rel and raw_rel != page_rel:
                raise SystemExit(f"{entry_id} night master {key} was rewritten")
        probe = dict(raw)
        resolved16 = str(scene.get("file_16x9_day") or "") or daylight_rel(raw, "16x9")
        if resolved16:
            probe["file_16x9_day"] = resolved16
        qualifies = is_genuine_daylight(probe)
        if qualifies and scene.get("daylight_primary") is not True:
            raise SystemExit(f"{entry_id} genuine daylight is not the card default")
        if scene.get("daylight_primary") and not qualifies:
            raise SystemExit(f"{entry_id} is daylight-primary without genuine-daylight provenance")
        if not scene.get("daylight_primary"):
            continue
        variant = scene.get("daylight_variant") or {}
        if variant.get("provenance") != "genuine-daylight":
            raise SystemExit(f"{entry_id} page payload lost genuine-daylight provenance")
        if not master_exists(scene.get("file_16x9_day")):
            raise SystemExit(f"{entry_id} daylight primary points at a missing master")


def assert_night_law(night: dict[str, list[str]], html: str) -> None:
    """Refuse a publish that invents a night plate or puts Night on a daylight card.

    Does not approve anything and does not write manifests, approvals, or QC notes.
    """
    if html.count("const GREECE_NIGHT=") != 1:
        raise SystemExit("GREECE_NIGHT was duplicated or dropped")
    if html.count('class="night-tab"') != 1:
        raise SystemExit("night button template was duplicated or dropped")
    keys = (("16x9", "file_16x9"), ("4x5", "file_4x5"), ("9x16", "file_9x16"))
    # Snapshot of this tree. A new night master must pass the same gate; this
    # count is the gate's output, not a list of invented plates.
    if len(night) != 44:
        raise SystemExit(f"expected 44 night cards, got {len(night)}")
    for banned in ("GR-01-008", "GR-01-046", "GR-01-062", "GR-01-088", "GR-01-117"):
        if banned in night:
            raise SystemExit(f"{banned} is not a night master and must not get Night")
    for required in ("GR-01-001", "GR-01-003", "GR-01-022", "GR-01-033"):
        urls = night.get(required)
        if not urls or len(urls) != 3 or not all(urls):
            raise SystemExit(f"{required} night record must be [16:9, 4:5, 9:16]")
    for entry_id, urls in night.items():
        if not isinstance(urls, list) or len(urls) != 3:
            raise SystemExit(f"{entry_id} night record must be [16:9, 4:5, 9:16]")
        raw = json.loads((ROOT / "manifests" / f"{entry_id}.json").read_text(encoding="utf-8"))
        variant = raw.get("daylight_variant")
        source = variant.get("source_night") if isinstance(variant, dict) else None
        if not isinstance(source, dict):
            source = {}
        weather = raw.get("weather")
        scene_night = (
            isinstance(weather, dict)
            and weather.get("is_day") == 0
            and lighting_label(raw) == "Night"
        )
        if not any(urls):
            raise SystemExit(f"{entry_id} has no night master on disk")
        for index, (fmt, key) in enumerate(keys):
            url = urls[index]
            scene_rel = str(raw.get(key) or "")
            if not url:
                continue
            if url != scene_rel:
                raise SystemExit(f"{entry_id} {fmt} night URL is not the scene master")
            if not master_exists(url):
                raise SystemExit(f"{entry_id} {fmt} night master missing on disk")
            if fmt == "9x16" and url == str(raw.get("file_16x9") or ""):
                raise SystemExit(f"{entry_id} invented a 9:16 night plate from 16:9")
            info = source.get(fmt) if isinstance(source.get(fmt), dict) else {}
            recorded = str(info.get("path") or "")
            recorded_match = bool(recorded) and recorded == scene_rel
            if not recorded_match and not scene_night:
                raise SystemExit(f"{entry_id} {fmt} night plate is not recorded")
        if lighting_label(raw) in ("Dawn", "Pre-dawn", "Daylight"):
            raise SystemExit(f"{entry_id} lighting label is not Night")


def main() -> None:
    tags = load_tags()
    scenes, meta, warnings = load_scenes(tags)
    html = render_html(scenes, meta)
    out = ROOT / "index.html"
    out.write_text(html, encoding="utf-8")
    thumbs = sum(1 for row in meta.values() if row[3])
    genuine = sum(1 for scene in scenes if scene.get("daylight_primary") is True)
    derivative = sum(
        1 for scene in scenes
        if scene.get("file_16x9_day") and scene.get("daylight_primary") is not True
    )
    night_only = sum(1 for scene in scenes if not scene.get("file_16x9_day"))
    night = load_night_masters()
    night_formats = {
        "16:9": sum(1 for urls in night.values() if urls[0]),
        "4:5": sum(1 for urls in night.values() if urls[1]),
        "9:16": sum(1 for urls in night.values() if urls[2]),
    }
    print(f"wrote index.html with {len(scenes)} scenes, {thumbs} related thumbs")
    print(
        f"daylight-primary {genuine}, sun toggle {derivative}, "
        f"no daylight file {night_only}"
    )
    print(
        f"night buttons {len(night)} of {len(scenes)} "
        f"(16:9={night_formats['16:9']} 4:5={night_formats['4:5']} 9:16={night_formats['9:16']})"
    )
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
