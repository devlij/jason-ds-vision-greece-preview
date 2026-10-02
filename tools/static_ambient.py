#!/usr/bin/env python3
"""Static-camera ambient clips for Greece 360 pack 1.

The camera stays locked on a genuine daylight 4:5 plate. The 190px label
bar under the photo is cropped off before any frame is made. Only sky,
water, foliage, and flags already in the plate are displaced, and only
inside their own masks, so architecture cannot smear, spawn, or flip.

This is not an orbit, a sweep, or an interpolation between generated views.
Image-to-video lateral bake is not used. Night masters are not used.
"""

from __future__ import annotations

import json
import math
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
WORK_ORDER = "wo-greece-360-2026-10-02"
PACK = (
    "GR-01-001",
    "GR-01-002",
    "GR-01-003",
    "GR-01-004",
    "GR-01-005",
    "GR-01-006",
    "GR-01-007",
    "GR-01-009",
    "GR-01-010",
    "GR-01-011",
    "GR-01-012",
    "GR-01-013",
)
# Night plates in this library sit well under this. Daylight plates sit well over it.
DAYLIGHT_TOP_V = 80.0


def scene_paths(entry_id: str) -> dict:
    slug = entry_id.lower()
    matches = sorted(ROOT.glob(f"library/world/Greece/**/{slug}-daylight-4x5.png"))
    if len(matches) != 1:
        raise SystemExit(f"{entry_id} daylight 4:5 masters found: {len(matches)}")
    anchor = matches[0]
    folder = anchor.parent
    return {
        "entry_id": entry_id,
        "anchor": anchor.relative_to(ROOT).as_posix(),
        "out": (folder / f"{slug}-motion-10s-4x5.mp4").relative_to(ROOT).as_posix(),
        "poster": (folder / f"{slug}-motion-10s-4x5-poster.jpg").relative_to(ROOT).as_posix(),
        "anchor_kind": "genuine-daylight 4:5 master; night master not used",
    }


def crop_plate(path: Path) -> np.ndarray:
    im = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit(f"missing anchor {path}")
    if im.shape[1] != PHOTO_W or im.shape[0] < PHOTO_H + 2:
        raise SystemExit(f"{path} is {im.shape[1]}x{im.shape[0]}, expected {PHOTO_W}x>={PHOTO_H + 2}")
    # Photo is the top 1080 rows. The 190px bar, including its hairline, starts at y=1080.
    plate = im[:PHOTO_H].copy()
    bar = im[PHOTO_H]
    edge = plate[-1]
    # A flat photo edge (dark water, shadow) is still the photo. Reject only when
    # that edge is the same flat color as the label bar, which means the crop landed in the bar.
    if float(edge.std()) < 4 and abs(float(edge.mean()) - float(bar.mean())) < 12:
        raise SystemExit(f"{path} bottom photo row looks like the label bar")
    hsv = cv2.cvtColor(plate, cv2.COLOR_BGR2HSV)
    top_v = float(hsv[:180, :, 2].mean())
    if top_v < DAYLIGHT_TOP_V:
        raise SystemExit(f"{path} top-band luminance {top_v:.1f} is not daylight")
    return plate


def _components(mask: np.ndarray, pred) -> np.ndarray:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
    keep = np.zeros(mask.shape, np.uint8)
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if pred(x, y, w, h, area):
            keep[labels == i] = 255
    return keep


def build_masks(plate: np.ndarray) -> dict[str, np.ndarray]:
    hsv = cv2.cvtColor(plate, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    height, width = h.shape
    yy = np.arange(height)[:, None]

    # Overcast skies are bright and dull. Late-afternoon skies in this set are a saturated blue.
    overcast = (s < 70) & (v > 145)
    # Aegean daylight skies in this library are a saturated blue (S often 210–255).
    # The Netherlands plates topped out nearer 180, so the same sky rule keeps the
    # hue band and drops only the saturation ceiling.
    blue_sky = (h >= 90) & (h <= 125) & (s >= 15) & (v > 145)
    sky_cand = (overcast | blue_sky).astype(np.uint8)
    sky_cand[(h >= 32) & (h <= 88) & (s > 48)] = 0
    sky_cand[((h < 12) | (h > 168)) & (s > 55)] = 0
    sky = _components(sky_cand, lambda x, y, w, hh, area: y <= 8 and area > 400)
    sky = cv2.erode(sky, np.ones((3, 3), np.uint8), iterations=1)

    # Blue-green water only. Dull stone and shadow must not enter the mask.
    blue_water = (h >= 88) & (h <= 128) & (s >= 40) & (s <= 180) & (v >= 35) & (v <= 185)
    water_cand = (blue_water & (sky == 0) & (yy > int(height * 0.28))).astype(np.uint8)
    water_cand[(h >= 35) & (h <= 88) & (s > 42)] = 0
    water = _components(
        water_cand,
        lambda x, y, w, hh, area: (
            area > 2200
            and w > 48
            and w > hh * 0.45
            and (y + hh / 2) > height * 0.40
        ),
    )
    water = cv2.erode(water, np.ones((3, 3), np.uint8), iterations=1)
    water = _components(
        water,
        lambda x, y, w, hh, area: area > 800 and w > 24 and hh < w * 2.0 and (y + hh / 2) > height * 0.45,
    )

    fol_cand = ((h >= 18) & (h <= 100) & (s >= 28) & (v >= 20) & (sky == 0) & (water == 0)).astype(np.uint8)
    foliage = _components(fol_cand, lambda x, y, w, hh, area: area > 120)
    foliage = cv2.erode(foliage, np.ones((3, 3), np.uint8), iterations=1)

    red = (((h <= 8) | (h >= 170)) & (s >= 150) & (v >= 100)).astype(np.uint8)
    blue = ((h >= 105) & (h <= 130) & (s >= 160) & (v >= 80) & (sky == 0)).astype(np.uint8)
    flag_cand = cv2.bitwise_or(red, blue)
    flag_cand[water > 0] = 0
    flags = _components(flag_cand, lambda x, y, w, hh, area: 40 <= area <= 4200 and hh < 180 and w < 160)
    flags = cv2.erode(flags, np.ones((2, 2), np.uint8), iterations=1)
    # A real flag in this detector is red cloth next to blue cloth. Pure blue
    # domes, doors, and windmill sails, and pure red roofs or columns, are
    # architecture and stay locked.
    flags = _bicolor_flags(flags, h)

    foliage[water > 0] = 0
    flags[foliage > 0] = 0
    flags[water > 0] = 0
    return {"sky": sky, "water": water, "foliage": foliage, "flags": flags}


def _bicolor_flags(mask: np.ndarray, hue: np.ndarray) -> np.ndarray:
    if not np.any(mask):
        return mask
    n, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=8)
    keep = np.zeros(mask.shape, np.uint8)
    for i in range(1, n):
        sel = labels == i
        red = bool(np.any((((hue <= 8) | (hue >= 170)) & sel)))
        blue = bool(np.any(((hue >= 105) & (hue <= 130) & sel)))
        if red and blue and int(stats[i, cv2.CC_STAT_AREA]) >= 40:
            keep[sel] = 255
    return keep


def _factor(mask: np.ndarray, reach: float) -> np.ndarray:
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 3)
    return np.clip(dist / reach, 0, 1).astype(np.float32)


def _apply(out: np.ndarray, plate: np.ndarray, mask: np.ndarray, dx: np.ndarray, dy: np.ndarray) -> None:
    if not np.any(mask):
        return
    height, width = mask.shape
    xs = np.broadcast_to(np.arange(width, dtype=np.float32), (height, width)).copy()
    ys = np.broadcast_to(np.arange(height, dtype=np.float32)[:, None], (height, width)).copy()
    map_x = xs - dx
    map_y = ys - dy
    warped = cv2.remap(plate, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    src = cv2.remap(mask.astype(np.float32) / 255.0, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    use = (mask > 0) & (src > 0.985)
    out[use] = warped[use]


def render_frame(plate: np.ndarray, masks: dict[str, np.ndarray], factors: dict[str, np.ndarray], n: int) -> np.ndarray:
    t = n / FRAMES
    # Every displacement is a sine that is 0 at frame 0 and frame FRAMES, so the loop closes.
    s1 = math.sin(2 * math.pi * t)
    s2 = math.sin(4 * math.pi * t)
    out = plate.copy()
    height, width = plate.shape[:2]
    ys = np.arange(height, dtype=np.float32)[:, None]
    xs = np.arange(width, dtype=np.float32)[None, :]

    if np.any(masks["foliage"]):
        phase = s1 * np.sin(ys * 0.035 + 0.4)
        dx = (4.6 * phase * factors["foliage"]).astype(np.float32)
        dy = (1.1 * s2 * factors["foliage"]).astype(np.float32)
        _apply(out, plate, masks["foliage"], dx, dy)

    if np.any(masks["water"]):
        dx = (3.4 * np.sin(2 * math.pi * t + ys * 0.045) * factors["water"]).astype(np.float32)
        dy = (1.6 * np.sin(4 * math.pi * t + xs * 0.05) * factors["water"]).astype(np.float32)
        _apply(out, plate, masks["water"], dx, dy)
        shimmer = (6.0 * np.sin(4 * math.pi * t + xs * 0.08 + ys * 0.03) * factors["water"]).astype(np.float32)
        region = masks["water"] > 0
        lifted = out.astype(np.float32)
        lifted[region] += shimmer[region, None]
        out[region] = np.clip(lifted[region], 0, 255).astype(np.uint8)

    if np.any(masks["flags"]):
        dx = (5.5 * np.sin(4 * math.pi * t + ys * 0.12) * factors["flags"]).astype(np.float32)
        dy = (1.2 * s2 * factors["flags"]).astype(np.float32)
        _apply(out, plate, masks["flags"], dx, dy)

    if np.any(masks["sky"]):
        dx = (22.0 * s1 * factors["sky"]).astype(np.float32)
        dy = (2.0 * s1 * factors["sky"]).astype(np.float32)
        _apply(out, plate, masks["sky"], dx, dy)
        breath = (10.0 * s1 * np.sin(xs * 0.03 + ys * 0.012) * factors["sky"]).astype(np.float32)
        region = masks["sky"] > 0
        lifted = out.astype(np.float32)
        lifted[region] += breath[region, None]
        out[region] = np.clip(lifted[region], 0, 255).astype(np.uint8)

    life = (masks["sky"] | masks["water"] | masks["foliage"] | masks["flags"]) > 0
    if not np.array_equal(out[~life], plate[~life]):
        raise SystemExit("architecture pixel moved; refusing to encode")
    return out


def factors_for(masks: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {
        "sky": _factor(masks["sky"], 32.0),
        "water": _factor(masks["water"], 14.0),
        "foliage": _factor(masks["foliage"], 16.0),
        "flags": _factor(masks["flags"], 6.0),
    }


def encode(plate: np.ndarray, masks: dict[str, np.ndarray], dest: Path) -> None:
    factors = factors_for(masks)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
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
            frame = render_frame(plate, masks, factors, n)
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise SystemExit(f"ffmpeg failed for {dest}\n{err[-2000:]}")


def write_poster(plate: np.ndarray, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(dest), plate, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise SystemExit(f"poster write failed {dest}")


def coverage(masks: dict[str, np.ndarray]) -> dict[str, float]:
    total = float(PHOTO_H * PHOTO_W)
    return {name: round(float(np.count_nonzero(mask)) / total, 4) for name, mask in masks.items()}


def life_phrase(cov: dict[str, float]) -> str:
    parts = []
    if cov.get("sky", 0) >= 0.01:
        parts.append("sky")
    if cov.get("water", 0) >= 0.005:
        parts.append("water")
    if cov.get("foliage", 0) >= 0.005:
        parts.append("foliage")
    if cov.get("flags", 0) >= 0.0005:
        parts.append("flags")
    if not parts:
        return "thin life mask"
    return ", ".join(parts) + "; architecture stays locked"


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
    if stream.get("codec_name") != "h264" or stream.get("pix_fmt") != "yuv420p":
        raise SystemExit(f"{dest} codec {stream.get('codec_name')} {stream.get('pix_fmt')}")
    if int(stream["width"]) != PHOTO_W or int(stream["height"]) != PHOTO_H:
        raise SystemExit(f"{dest} dims {stream['width']}x{stream['height']}")
    if abs(duration - 10.0) > 0.05:
        raise SystemExit(f"{dest} duration {duration}")
    if stream.get("avg_frame_rate") not in {"24/1", "24"}:
        raise SystemExit(f"{dest} fps {stream.get('avg_frame_rate')}")
    return {
        "duration_s": round(duration, 3),
        "width": PHOTO_W,
        "height": PHOTO_H,
        "codec": "h264",
        "pix_fmt": "yuv420p",
        "faststart": True,
    }


def encoded_motion_stats(dest: Path, plate: np.ndarray, masks: dict[str, np.ndarray]) -> dict:
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(dest), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        check=True,
        capture_output=True,
    )
    frames = np.frombuffer(proc.stdout, dtype=np.uint8)
    expect = FRAMES * PHOTO_H * PHOTO_W * 3
    if frames.size != expect:
        raise SystemExit(f"{dest} decoded {frames.size} bytes, expected {expect}")
    frames = frames.reshape(FRAMES, PHOTO_H, PHOTO_W, 3)
    life = (masks["sky"] | masks["water"] | masks["foliage"] | masks["flags"]) > 0
    locked = ~life

    def mad(frame: np.ndarray, region: np.ndarray) -> float:
        delta = cv2.absdiff(frame, plate)
        return round(float(delta[region].mean()), 3)

    locked_mads = {str(n): mad(frames[n], locked) for n in (0, 60, 120, 239)}
    peak = mad(frames[60], np.ones(locked.shape, dtype=bool))
    spread = max(locked_mads.values()) - min(locked_mads.values())
    if spread > 1.0:
        raise SystemExit(f"{dest} architecture MAD is not flat: {locked_mads}")
    return {
        "architecture_mad_flat": True,
        "locked_mad": locked_mads,
        "peak_frame_mad": peak,
        "frames": FRAMES,
    }


def caption_of(entry_id: str) -> str:
    raw = json.loads((ROOT / "manifests" / f"{entry_id}.json").read_text(encoding="utf-8"))
    return str(raw.get("caption") or "")


def update_manifest(scene: dict, row: dict) -> None:
    path = ROOT / "manifests" / f"{scene['entry_id']}.json"
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    # Clip record only. Scene approval, QC notes, and status stay as they are.
    data["file_motion_10s_4x5"] = scene["out"]
    data["file_motion_poster"] = scene["poster"]
    data["motion_clip"] = {
        "status": "Candidate",
        "work_order": WORK_ORDER,
        "pack": 1,
        "method": "static-ambient",
        "duration_s": 10.0,
        "width": PHOTO_W,
        "height": PHOTO_H,
        "fps": FPS,
        "format": "4:5",
        "camera": "locked",
        "anchor": scene["anchor"],
        "anchor_kind": scene["anchor_kind"],
        "label_bar_px_cropped": 190,
        "life": row["life"],
        "pedestrians": "Left on the locked plate. A synthetic walk would invent limbs.",
        "forbidden_method_not_used": "orbit, sweep, viewpoint interpolation, optical-flow blend, pan/zoom drift",
        "qc": "Candidate only. Not Cosmo QC. Not approved. Do not merge.",
    }
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if original.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def hold(scene: dict, reason: str, attempts: int) -> dict:
    for rel in (scene["out"], scene["poster"]):
        path = ROOT / rel
        if path.is_file():
            path.unlink()
    return {
        "entry_id": scene["entry_id"],
        "caption": caption_of(scene["entry_id"]),
        "status": "HOLD",
        "attempts": attempts,
        "reason": reason,
    }


def produce(scene: dict) -> dict:
    plate = crop_plate(ROOT / scene["anchor"])
    masks = build_masks(plate)
    cov = coverage(masks)
    life = sum(cov.values())
    if life < 0.04:
        raise SystemExit(f"life coverage {life:.4f} is too thin for static ambient")
    last_error = "unknown"
    for attempt in (1, 2):
        try:
            encode(plate, masks, ROOT / scene["out"])
            write_poster(plate, ROOT / scene["poster"])
            probed = probe(ROOT / scene["out"])
            stats = encoded_motion_stats(ROOT / scene["out"], plate, masks)
            row = {
                "entry_id": scene["entry_id"],
                "caption": caption_of(scene["entry_id"]),
                "status": "Candidate",
                "method": "static-ambient",
                "attempts": attempt,
                "anchor": scene["anchor"],
                "anchor_kind": scene["anchor_kind"],
                "out": scene["out"],
                "poster": scene["poster"],
                "coverage": cov,
                "life": life_phrase(cov),
                **probed,
                **stats,
            }
            update_manifest(scene, row)
            return row
        except SystemExit as exc:
            last_error = str(exc)
            print(f"HOLD-attempt {scene['entry_id']} try {attempt}: {last_error}", file=sys.stderr)
    return hold(scene, last_error, 2)


def debug_scene(scene: dict) -> dict:
    plate = crop_plate(ROOT / scene["anchor"])
    masks = build_masks(plate)
    cov = coverage(masks)
    hsv = cv2.cvtColor(plate, cv2.COLOR_BGR2HSV)
    return {
        "entry_id": scene["entry_id"],
        "caption": caption_of(scene["entry_id"]),
        "anchor": scene["anchor"],
        "coverage": cov,
        "life_sum": round(sum(cov.values()), 4),
        "top_v": round(float(hsv[:180, :, 2].mean()), 1),
        "mean_v": round(float(hsv[:, :, 2].mean()), 1),
    }


def main() -> None:
    debug = "--debug" in sys.argv
    only = [a for a in sys.argv[1:] if a.startswith("GR-")]
    scenes = [scene_paths(entry_id) for entry_id in PACK if not only or entry_id in only]
    rows = []
    holds = []
    for scene in scenes:
        if debug:
            try:
                row = debug_scene(scene)
            except SystemExit as exc:
                row = {"entry_id": scene["entry_id"], "error": str(exc)}
            print(json.dumps(row))
            rows.append(row)
            continue
        try:
            row = produce(scene)
        except SystemExit as exc:
            row = hold(scene, str(exc), 1)
        print(json.dumps({k: row[k] for k in ("entry_id", "status", "attempts") if k in row} | ({"reason": row["reason"]} if row.get("status") == "HOLD" else {"out": row.get("out")})))
        if row.get("status") == "HOLD":
            holds.append(row)
        else:
            rows.append(row)
    if debug:
        return
    evidence = {
        "work_order": WORK_ORDER,
        "pack": 1,
        "status": "Candidate",
        "qc": "Not Cosmo QC. Not approved. Do not merge.",
        "method": "static-ambient",
        "camera": "locked",
        "i2v": "unavailable fleet-wide; lateral-sweep bake-path not used",
        "not_used": [
            "orbit",
            "sweep",
            "viewpoint interpolation",
            "optical-flow blend between generated views",
            "pan/zoom drift",
            "night master",
            "finished master with the label bar left on",
        ],
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
        },
        "player": "controls=false, autoplay, muted, loop, playsinline, custom 360° / Close. Button only when the mp4 exists.",
        "skipped_no_daylight_master": ["GR-01-008"],
        "holds": holds,
        "scenes": rows,
    }
    dest = ROOT / "evidence" / "motion" / "GR-360-pack1-2026-10-02.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest} clips={len(rows)} holds={len(holds)}")


if __name__ == "__main__":
    main()
