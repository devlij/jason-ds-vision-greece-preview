#!/usr/bin/env python3
"""Greece 360 kickoff pack 2 — static-ambient Ken Burns clips.

Daylight scenes only. A night scenario never gets a clip, and a derivative
daylight plate of a night scene is not a source. Pack 1 clips stay on disk.
The next 12 daylight scenes that do not already have a
``*-motion-10s-4x5.mp4`` are encoded.

Source is that scene's 4:5 master. The 190px label bar under the photo is
cropped off (864×1080 from the top). ffmpeg then stores a 10.0s 864×1080
h264 Ken Burns lateral pan-zoom. Real image-to-video is later.

One self-QC failure holds that scene and the pack moves on. Three holds in
a row stop the pack and the evidence file is an escalate report. Nothing
here is Cosmo QC, and no scene is promoted to Approved.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FPS = 24
FRAMES = 240  # exactly 10.0s
PHOTO_H = 1080
PHOTO_W = 864
PACK_LIMIT = 12
PACK = 2
WORK_ORDER = "wo-greece-360-kickoff-2026-10-05"
EVIDENCE_NAME = "GR-360-kickoff-pack2-2026-10-05.json"
HOUR_RE = re.compile(r"(\d{1,2}):(\d{2})")
FROZEN_KEYS = (
    "approval_status",
    "qc_status",
    "qc_notes",
    "approved_at",
    "approval_basis",
)
# Daylight plates in this library sit well over this. A night plate does not.
DAYLIGHT_TOP_MEAN = 80.0
# Encoded motion between the rest pose and the lateral pose. Below this the
# clip is effectively still. Above this the window jumped.
MOTION_MAD_MIN = 4.0
MOTION_MAD_MAX = 48.0


def is_daylight(label: str) -> bool:
    """07:00–18:59 is day. Every other hour, and a missing hour, is night."""
    match = HOUR_RE.search(label or "")
    if not match:
        return False
    hour = int(match.group(1))
    if hour > 23:
        return False
    return 7 <= hour <= 18


def motion_paths(entry_id: str) -> list[Path]:
    slug = entry_id.lower()
    return sorted(ROOT.glob(f"**/{slug}-motion-10s-4x5.mp4"))


def load_manifests() -> list[dict]:
    rows = []
    for path in sorted((ROOT / "manifests").glob("GR-*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        entry_id = str(raw.get("entry_id") or "")
        if not entry_id:
            raise SystemExit(f"{path.name} has no entry_id")
        rows.append(raw)
    rows.sort(key=lambda item: item["entry_id"])
    return rows


def select_pack(manifests: list[dict]) -> tuple[list[dict], list[str], list[str]]:
    """First 12 daylight scenes, lowest id, that lack a motion mp4.

    Night scenes are counted and then ignored. They are never candidates.
    """
    daylight_missing: list[str] = []
    night: list[str] = []
    chosen: list[dict] = []
    for raw in manifests:
        entry_id = raw["entry_id"]
        if not is_daylight(str(raw.get("scenario_label") or "")):
            night.append(entry_id)
            continue
        if motion_paths(entry_id):
            continue
        daylight_missing.append(entry_id)
        if len(chosen) < PACK_LIMIT:
            anchor = str(raw.get("file_4x5") or "")
            slug = entry_id.lower()
            chosen.append({
                "entry_id": entry_id,
                "caption": str(raw.get("caption") or ""),
                "scenario_label": str(raw.get("scenario_label") or ""),
                "anchor": anchor,
                "anchor_kind": "daylight 4:5 master; label bar cropped; night master not used",
                "out": f"assets/{slug}-motion-10s-4x5.mp4",
                "poster": f"assets/{slug}-motion-10s-4x5-poster.jpg",
            })
    return chosen, daylight_missing, night


def crop_plate(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"missing 4:5 master {path}")
    height, width = image.shape[:2]
    if width != PHOTO_W or height < PHOTO_H + 2:
        raise SystemExit(f"{path} is {width}x{height}, expected {PHOTO_W}x>{PHOTO_H}")
    plate = image[:PHOTO_H].copy()
    hairline = image[PHOTO_H]
    edge = plate[-1]
    # The label bar opens with a flat light hairline at y=1080. Landing in
    # the bar, or missing it, is a failed crop.
    if float(hairline.std()) > 12 or float(hairline.mean()) < 180:
        raise SystemExit(
            f"{path} row {PHOTO_H} is not the label-bar hairline "
            f"(mean {float(hairline.mean()):.1f}, std {float(hairline.std()):.1f})"
        )
    if float(edge.std()) < 4 and abs(float(edge.mean()) - float(hairline.mean())) < 12:
        raise SystemExit(f"{path} bottom photo row looks like the label bar")
    top = float(plate[:180].mean())
    if top < DAYLIGHT_TOP_MEAN:
        raise SystemExit(f"{path} top-band luminance {top:.1f} is not daylight")
    return plate


def pose(n: int) -> tuple[float, float, float]:
    """Loop-closing Ken Burns. Frame 0 and frame FRAMES share one pose.

    Zoom eases in and back. The window also eases to the right, back
    through center, to the left, and home, so the lateral pan loops.
    """
    t = n / FRAMES
    zoom_wave = math.sin(math.pi * t)
    pan_wave = math.sin(2 * math.pi * t)
    zoom = 1.05 + 0.07 * zoom_wave
    return zoom, pan_wave, zoom_wave


def render_frame(plate: np.ndarray, n: int) -> np.ndarray:
    zoom, pan_wave, zoom_wave = pose(n)
    win_w = PHOTO_W / zoom
    win_h = PHOTO_H / zoom
    slack_x = PHOTO_W - win_w
    slack_y = PHOTO_H - win_h
    x0 = slack_x * (0.5 + 0.42 * pan_wave)
    y0 = slack_y * (0.5 + 0.12 * zoom_wave)
    xs = np.arange(PHOTO_W, dtype=np.float32)
    ys = np.arange(PHOTO_H, dtype=np.float32)
    map_x = np.broadcast_to(
        (x0 + (xs + 0.5) * (win_w / PHOTO_W) - 0.5).astype(np.float32),
        (PHOTO_H, PHOTO_W),
    ).copy()
    map_y = np.broadcast_to(
        (y0 + (ys + 0.5) * (win_h / PHOTO_H) - 0.5).astype(np.float32)[:, None],
        (PHOTO_H, PHOTO_W),
    ).copy()
    if (
        float(map_x.min()) < 0
        or float(map_x.max()) > PHOTO_W - 1
        or float(map_y.min()) < 0
        or float(map_y.max()) > PHOTO_H - 1
    ):
        raise SystemExit("Ken Burns window left the 4:5 plate")
    return cv2.remap(plate, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def encode(plate: np.ndarray, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{PHOTO_W}x{PHOTO_H}",
        "-r", str(FPS),
        "-i", "-",
        "-an",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "medium",
        "-movflags", "+faststart",
        str(dest),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for n in range(FRAMES):
            proc.stdin.write(np.ascontiguousarray(render_frame(plate, n)).tobytes())
    finally:
        proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise SystemExit(f"ffmpeg failed for {dest}\n{err[-2000:]}")


def write_poster(plate: np.ndarray, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(dest), render_frame(plate, 0), [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise SystemExit(f"poster write failed {dest}")


def probe(dest: Path) -> dict:
    raw = dest.read_bytes()
    moov = raw.find(b"moov")
    mdat = raw.find(b"mdat")
    if moov < 0 or mdat < 0 or moov > mdat:
        raise SystemExit(f"{dest} is not faststart (moov {moov}, mdat {mdat})")
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height,pix_fmt,nb_frames,avg_frame_rate",
            "-show_entries", "format=duration",
            "-of", "json",
            str(dest),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    info = json.loads(proc.stdout)
    stream = info["streams"][0]
    duration = float(info["format"]["duration"])
    frames = int(stream.get("nb_frames") or 0)
    if stream.get("codec_name") != "h264" or stream.get("pix_fmt") != "yuv420p":
        raise SystemExit(f"{dest} codec {stream.get('codec_name')} {stream.get('pix_fmt')}")
    if int(stream["width"]) != PHOTO_W or int(stream["height"]) != PHOTO_H:
        raise SystemExit(f"{dest} dims {stream['width']}x{stream['height']}")
    if abs(duration - 10.0) > 0.05:
        raise SystemExit(f"{dest} duration {duration}")
    if stream.get("avg_frame_rate") not in {"24/1", "24"}:
        raise SystemExit(f"{dest} fps {stream.get('avg_frame_rate')}")
    if frames != FRAMES:
        raise SystemExit(f"{dest} frames {frames}")
    return {
        "duration_s": round(duration, 3),
        "width": PHOTO_W,
        "height": PHOTO_H,
        "codec": "h264",
        "pix_fmt": "yuv420p",
        "faststart": True,
        "frames": FRAMES,
    }


def _mad(a: np.ndarray, b: np.ndarray) -> float:
    return float(cv2.absdiff(a, b).mean())


def qc_clip(dest: Path, plate: np.ndarray) -> dict:
    """One pass. A miss here is the scene's only attempt."""
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(dest), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        check=True,
        capture_output=True,
    )
    raw = np.frombuffer(proc.stdout, dtype=np.uint8)
    expect = FRAMES * PHOTO_H * PHOTO_W * 3
    if raw.size != expect:
        raise SystemExit(f"{dest} decoded {raw.size} bytes, expected {expect}")
    frames = raw.reshape(FRAMES, PHOTO_H, PHOTO_W, 3)
    bottom = frames[0, -1]
    if float(bottom.std()) < 12 and float(bottom.mean()) > 180:
        raise SystemExit(f"{dest} bottom row still looks like the label-bar hairline")
    # The lateral pose is a quarter of the way through. The zoom peaks at the middle.
    lateral = _mad(frames[0], frames[60])
    zoomed = _mad(frames[0], frames[120])
    if lateral < MOTION_MAD_MIN and zoomed < MOTION_MAD_MIN:
        raise SystemExit(f"{dest} Ken Burns motion too small (lateral {lateral:.2f}, zoom {zoomed:.2f})")
    if lateral > MOTION_MAD_MAX or zoomed > MOTION_MAD_MAX:
        raise SystemExit(f"{dest} Ken Burns motion too large (lateral {lateral:.2f}, zoom {zoomed:.2f})")
    rest = render_frame(plate, 0)
    home = render_frame(plate, FRAMES)
    if _mad(rest, home) > 0.05:
        raise SystemExit("Ken Burns pose does not close the loop")
    return {
        "lateral_mad": round(lateral, 3),
        "zoom_mad": round(zoomed, 3),
        "camera": "ken-burns lateral pan-zoom",
        "zoom": "1.05 to 1.12 and back",
        "pan": "lateral, 84% of the zoom slack, and back",
    }


def update_manifest(scene: dict, row: dict) -> None:
    path = ROOT / "manifests" / f"{scene['entry_id']}.json"
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    frozen = {key: data.get(key) for key in FROZEN_KEYS}
    data["file_motion_10s_4x5"] = scene["out"]
    data["file_motion_poster"] = scene["poster"]
    data["motion_clip"] = {
        "status": "Candidate",
        "work_order": WORK_ORDER,
        "pack": PACK,
        "method": "static-ambient",
        "duration_s": 10.0,
        "width": PHOTO_W,
        "height": PHOTO_H,
        "fps": FPS,
        "format": "4:5",
        "camera": "ken-burns lateral pan-zoom",
        "anchor": scene["anchor"],
        "anchor_kind": scene["anchor_kind"],
        "label_bar_px_cropped": 190,
        "qc": "Candidate only. Not Cosmo QC. Not approved. Do not merge.",
        "i2v": "later",
    }
    if {key: data.get(key) for key in FROZEN_KEYS} != frozen:
        raise SystemExit(f"{scene['entry_id']} approval fields changed")
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if original.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def hold(scene: dict, reason: str) -> dict:
    reason = reason.replace(str(ROOT) + "/", "")
    for rel in (scene["out"], scene["poster"]):
        path = ROOT / rel
        if path.is_file():
            path.unlink()
    return {
        "entry_id": scene["entry_id"],
        "caption": scene["caption"],
        "scenario_label": scene["scenario_label"],
        "status": "HOLD",
        "attempts": 1,
        "reason": reason,
        "anchor": scene["anchor"],
    }


def produce(scene: dict) -> dict:
    if not is_daylight(scene["scenario_label"]):
        raise SystemExit("night scene reached the encoder")
    plate = crop_plate(ROOT / scene["anchor"])
    encode(plate, ROOT / scene["out"])
    write_poster(plate, ROOT / scene["poster"])
    probed = probe(ROOT / scene["out"])
    motion = qc_clip(ROOT / scene["out"], plate)
    row = {
        "entry_id": scene["entry_id"],
        "caption": scene["caption"],
        "scenario_label": scene["scenario_label"],
        "status": "Candidate",
        "method": "static-ambient",
        "attempts": 1,
        "anchor": scene["anchor"],
        "anchor_kind": scene["anchor_kind"],
        "out": scene["out"],
        "poster": scene["poster"],
        **probed,
        **motion,
    }
    update_manifest(scene, row)
    return row


def debug_scene(scene: dict) -> dict:
    plate = crop_plate(ROOT / scene["anchor"])
    rest = render_frame(plate, 0)
    lateral = render_frame(plate, 60)
    zoomed = render_frame(plate, 120)
    return {
        "entry_id": scene["entry_id"],
        "caption": scene["caption"],
        "anchor": scene["anchor"],
        "top_mean": round(float(plate[:180].mean()), 2),
        "lateral_mad": round(_mad(rest, lateral), 3),
        "zoom_mad": round(_mad(rest, zoomed), 3),
        "loop_mad": round(_mad(rest, render_frame(plate, FRAMES)), 4),
    }


def remaining_daylight(manifests: list[dict]) -> list[str]:
    missing = []
    for raw in manifests:
        entry_id = raw["entry_id"]
        if not is_daylight(str(raw.get("scenario_label") or "")):
            continue
        if not motion_paths(entry_id):
            missing.append(entry_id)
    return missing


def write_evidence(
    scenes: list[dict],
    holds: list[dict],
    not_attempted: list[str],
    night: list[str],
    manifests: list[dict],
    escalated: bool,
) -> Path:
    remaining = remaining_daylight(manifests)
    evidence = {
        "work_order": WORK_ORDER,
        "pack": PACK,
        "name": "Greece 360 kickoff pack 2",
        "status": "ESCALATE" if escalated else "Candidate",
        "qc": "Not Cosmo QC. Not approved. Do not merge.",
        "method": "static-ambient",
        "camera": "ken-burns lateral pan-zoom",
        "i2v": "later",
        "night_policy": "Night scenes never get a clip. Night masters were not used.",
        "night_scenes_skipped": night,
        "spec": {
            "duration_s": 10.0,
            "width": PHOTO_W,
            "height": PHOTO_H,
            "fps": FPS,
            "format": "4:5",
            "codec": "h264",
            "pix_fmt": "yuv420p",
            "faststart": True,
            "label_bar_px_cropped": 190,
            "crop": "864:1080:0:0",
            "source": "daylight 4:5 master",
        },
        "player": "controls=false, autoplay, muted, loop, playsinline, custom 360° / Close. Button only when the mp4 exists.",
        "fail_policy": "One self-QC failure holds the scene. Three holds in a row stop the pack.",
        "escalated": escalated,
        "holds": holds,
        "scenes": scenes,
        "not_attempted": not_attempted,
        "remaining_daylight_without_clips": remaining,
        "remaining_daylight_without_clips_count": len(remaining),
    }
    dest = ROOT / "evidence" / "motion" / EVIDENCE_NAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest


def main() -> None:
    debug = "--debug" in sys.argv
    manifests = load_manifests()
    chosen, _missing, night = select_pack(manifests)
    if any(not is_daylight(scene["scenario_label"]) for scene in chosen):
        raise SystemExit("selector returned a night scene")
    if debug:
        for scene in chosen:
            try:
                print(json.dumps(debug_scene(scene)))
            except SystemExit as exc:
                print(json.dumps({"entry_id": scene["entry_id"], "error": str(exc)}))
        return

    scenes: list[dict] = []
    holds: list[dict] = []
    streak = 0
    escalated = False
    attempted = 0
    for scene in chosen:
        attempted += 1
        try:
            row = produce(scene)
        except SystemExit as exc:
            row = hold(scene, str(exc))
        print(json.dumps({
            "entry_id": row["entry_id"],
            "status": row["status"],
            "attempts": row["attempts"],
            **({"reason": row["reason"]} if row["status"] == "HOLD" else {"out": row["out"]}),
        }))
        if row["status"] == "HOLD":
            holds.append(row)
            streak += 1
            if streak >= 3:
                escalated = True
                break
        else:
            scenes.append(row)
            streak = 0
    not_attempted = [scene["entry_id"] for scene in chosen[attempted:]]
    dest = write_evidence(scenes, holds, not_attempted, night, manifests, escalated)
    print(
        f"wrote {dest} clips={len(scenes)} holds={len(holds)} "
        f"escalated={escalated} not_attempted={len(not_attempted)}"
    )
    if escalated:
        raise SystemExit("ESCALATE: 3 holds in a row")


if __name__ == "__main__":
    main()
