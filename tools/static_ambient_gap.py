#!/usr/bin/env python3
"""Finish the Greece 360 daylight gap with static-ambient Ken Burns clips.

Stacked on kickoff pack 2. Every remaining daylight scene that has no
``*-motion-10s-4x5.mp4`` is encoded once. Night scenes are never encoded.
Prior HOLDs (GR-01-108) are not retried. A failed scene is marked HOLD and
the run moves on. Three consecutive different-scene failures stop the run.

Source is that scene's own 4:5 master. The 190px label bar is cropped off
(864×1080 from the top). ffmpeg stores a 10.0s 864×1080 24fps h264 Ken Burns
lateral pan-zoom. The daylight luminance floor is pack 2's top-band mean of
80. Clip records stay Candidate. Nothing here is Cosmo QC.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path

import numpy as np

import static_ambient as sa

PACK = 3
WORK_ORDER = sa.WORK_ORDER
EVIDENCE_NAME = "GR-360-kickoff-daylight-gap-2026-10-05.json"
EVIDENCE_PATH = sa.ROOT / "evidence" / "motion" / EVIDENCE_NAME
PRIOR_EVIDENCE = (
    "GR-360-kickoff-pack1-2026-10-05.json",
    "GR-360-kickoff-pack2-2026-10-05.json",
)


def qc_clip_light(dest: Path, plate: np.ndarray) -> dict:
    """Same checks as pack 2, reading frames 0, 60, and 120 only."""
    proc = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-i", str(dest),
            "-vf", r"select=eq(n\,0)+eq(n\,60)+eq(n\,120)",
            "-vsync", "vfr",
            "-frames:v", "3",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-",
        ],
        check=True,
        capture_output=True,
    )
    raw = np.frombuffer(proc.stdout, dtype=np.uint8)
    frame_bytes = sa.PHOTO_H * sa.PHOTO_W * 3
    if raw.size != frame_bytes * 3:
        raise SystemExit(f"{dest} sampled {raw.size} bytes, expected {frame_bytes * 3}")
    frames = raw.reshape(3, sa.PHOTO_H, sa.PHOTO_W, 3)
    bottom = frames[0, -1]
    if float(bottom.std()) < 12 and float(bottom.mean()) > 180:
        raise SystemExit(f"{dest} bottom row still looks like the label-bar hairline")
    lateral = sa._mad(frames[0], frames[1])
    zoomed = sa._mad(frames[0], frames[2])
    if lateral < sa.MOTION_MAD_MIN and zoomed < sa.MOTION_MAD_MIN:
        raise SystemExit(
            f"{dest} Ken Burns motion too small (lateral {lateral:.2f}, zoom {zoomed:.2f})"
        )
    if lateral > sa.MOTION_MAD_MAX or zoomed > sa.MOTION_MAD_MAX:
        raise SystemExit(
            f"{dest} Ken Burns motion too large (lateral {lateral:.2f}, zoom {zoomed:.2f})"
        )
    rest = sa.render_frame(plate, 0)
    home = sa.render_frame(plate, sa.FRAMES)
    if sa._mad(rest, home) > 0.05:
        raise SystemExit("Ken Burns pose does not close the loop")
    return {
        "lateral_mad": round(lateral, 3),
        "zoom_mad": round(zoomed, 3),
        "camera": "ken-burns lateral pan-zoom",
        "zoom": "1.05 to 1.12 and back",
        "pan": "lateral, 84% of the zoom slack, and back",
    }


def scene_from_manifest(raw: dict) -> dict:
    entry_id = raw["entry_id"]
    slug = entry_id.lower()
    return {
        "entry_id": entry_id,
        "caption": str(raw.get("caption") or ""),
        "scenario_label": str(raw.get("scenario_label") or ""),
        "anchor": str(raw.get("file_4x5") or ""),
        "anchor_kind": "daylight 4:5 master; label bar cropped; night master not used",
        "out": f"assets/{slug}-motion-10s-4x5.mp4",
        "poster": f"assets/{slug}-motion-10s-4x5-poster.jpg",
    }


def load_prior() -> tuple[set[str], set[str], list[dict]]:
    """Pack 1 and 2 shipped ids, their hold ids, and the hold rows."""
    shipped: set[str] = set()
    holds: set[str] = set()
    hold_rows: list[dict] = []
    for name in PRIOR_EVIDENCE:
        path = sa.ROOT / "evidence" / "motion" / name
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("scenes") or []:
            shipped.add(row["entry_id"])
        for row in data.get("holds") or []:
            holds.add(row["entry_id"])
            hold_rows.append(row)
    return shipped, holds, hold_rows


def night_ids(manifests: list[dict]) -> list[str]:
    return [
        raw["entry_id"]
        for raw in manifests
        if not sa.is_daylight(str(raw.get("scenario_label") or ""))
    ]


def load_checkpoint() -> tuple[list[dict], list[dict], bool]:
    if not EVIDENCE_PATH.is_file():
        return [], [], False
    data = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    return list(data.get("scenes") or []), list(data.get("holds") or []), bool(data.get("escalated"))


def write_manifest(path: Path, data: dict, original: str) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if original.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def assign_pack(entry_id: str) -> None:
    path = sa.ROOT / "manifests" / f"{entry_id}.json"
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    frozen = {key: data.get(key) for key in sa.FROZEN_KEYS}
    clip = data.get("motion_clip")
    if not isinstance(clip, dict):
        raise SystemExit(f"{entry_id} clip record missing while assigning pack")
    clip["pack"] = PACK
    clip["status"] = "Candidate"
    clip["method"] = "static-ambient"
    clip["work_order"] = WORK_ORDER
    data["motion_clip"] = clip
    if {key: data.get(key) for key in sa.FROZEN_KEYS} != frozen:
        raise SystemExit(f"{entry_id} approval fields changed")
    write_manifest(path, data, original)


def revert_motion(scene: dict) -> None:
    for rel in (scene["out"], scene["poster"]):
        path = sa.ROOT / rel
        if path.is_file():
            path.unlink()
    path = sa.ROOT / "manifests" / f"{scene['entry_id']}.json"
    if not path.is_file():
        return
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    frozen = {key: data.get(key) for key in sa.FROZEN_KEYS}
    if data.get("file_motion_10s_4x5") != scene["out"]:
        return
    data.pop("file_motion_10s_4x5", None)
    data.pop("file_motion_poster", None)
    data.pop("motion_clip", None)
    if {key: data.get(key) for key in sa.FROZEN_KEYS} != frozen:
        raise SystemExit(f"{scene['entry_id']} approval fields changed while reverting")
    write_manifest(path, data, original)


def rehydrate(scene: dict) -> dict:
    """Measure an already-written clip and record it on this pack. No re-encode."""
    if not sa.is_daylight(scene["scenario_label"]):
        raise SystemExit("night scene reached rehydrate")
    plate = sa.crop_plate(sa.ROOT / scene["anchor"])
    probed = sa.probe(sa.ROOT / scene["out"])
    motion = sa.qc_clip(sa.ROOT / scene["out"], plate)
    assign_pack(scene["entry_id"])
    return {
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


def run_one(scene: dict) -> dict:
    try:
        return sa.produce(scene)
    except SystemExit as exc:
        return sa.hold(scene, str(exc))
    except Exception as exc:
        return sa.hold(scene, f"{type(exc).__name__}: {exc}")


def write_evidence(
    scenes: list[dict],
    holds: list[dict],
    not_attempted: list[str],
    prior_hold_rows: list[dict],
    night: list[str],
    manifests: list[dict],
    escalated: bool,
) -> None:
    remaining = sa.remaining_daylight(manifests)
    evidence = {
        "work_order": WORK_ORDER,
        "pack": PACK,
        "name": "Greece 360 daylight gap",
        "stacked_on": "cursor/greece-360-kickoff-pack2-6970",
        "status": "ESCALATE" if escalated else "Candidate",
        "qc": "Not Cosmo QC. Not approved. Do not merge.",
        "method": "static-ambient",
        "camera": "ken-burns lateral pan-zoom",
        "i2v": "later",
        "night_policy": "Night scenes never get a clip. Night masters were not used.",
        "night_scenes_skipped": night,
        "spec": {
            "duration_s": 10.0,
            "width": sa.PHOTO_W,
            "height": sa.PHOTO_H,
            "fps": sa.FPS,
            "format": "4:5",
            "codec": "h264",
            "pix_fmt": "yuv420p",
            "faststart": True,
            "label_bar_px_cropped": 190,
            "crop": "864:1080:0:0",
            "source": "daylight 4:5 master",
            "daylight_top_mean_min": sa.DAYLIGHT_TOP_MEAN,
        },
        "player": "controls=false, autoplay, muted, loop, playsinline, custom 360° / Close. Button only when the mp4 exists.",
        "fail_policy": "One self-QC failure holds the scene. Three holds in a row stop the pack.",
        "escalated": escalated,
        "prior_holds_not_retried": prior_hold_rows,
        "holds": holds,
        "scenes": scenes,
        "not_attempted": not_attempted,
        "remaining_daylight_without_clips": remaining,
        "remaining_daylight_without_clips_count": len(remaining),
    }
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def select_next(manifests: list[dict], skip: set[str], limit: int) -> list[dict]:
    chosen: list[dict] = []
    for raw in manifests:
        entry_id = raw["entry_id"]
        if entry_id in skip:
            continue
        if not sa.is_daylight(str(raw.get("scenario_label") or "")):
            continue
        if sa.motion_paths(entry_id):
            continue
        chosen.append(scene_from_manifest(raw))
        if len(chosen) >= limit:
            break
    return chosen


def orphans(manifests: list[dict], known: set[str]) -> list[dict]:
    rows = []
    for raw in manifests:
        entry_id = raw["entry_id"]
        if entry_id in known:
            continue
        if not sa.is_daylight(str(raw.get("scenario_label") or "")):
            continue
        if not sa.motion_paths(entry_id):
            continue
        rows.append(scene_from_manifest(raw))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    if args.limit < 1 or args.workers < 1:
        raise SystemExit("limit and workers must be positive")

    sa.PACK = PACK
    sa.qc_clip = qc_clip_light

    manifests = sa.load_manifests()
    night = night_ids(manifests)
    prior_shipped, prior_hold_ids, prior_hold_rows = load_prior()
    scenes, holds, already_escalated = load_checkpoint()
    if already_escalated:
        print("already escalated; not encoding more")
        raise SystemExit("ESCALATE: 3 holds in a row")

    known = prior_shipped | prior_hold_ids | {row["entry_id"] for row in scenes} | {row["entry_id"] for row in holds}
    for scene in orphans(manifests, known):
        row = rehydrate(scene)
        scenes.append(row)
        print(json.dumps({"entry_id": row["entry_id"], "status": "Candidate", "adopted": True, "out": row["out"]}))
    scenes.sort(key=lambda row: row["entry_id"])

    skip = set(known) | {row["entry_id"] for row in scenes}
    chosen = select_next(manifests, skip, args.limit)
    if any(not sa.is_daylight(scene["scenario_label"]) for scene in chosen):
        raise SystemExit("selector returned a night scene")

    streak = 0
    escalated = False
    not_attempted: list[str] = []
    completed: dict[int, dict] = {}
    next_take = 0
    next_i = 0
    inflight = {}

    def submit_more(pool: ThreadPoolExecutor) -> None:
        nonlocal next_i
        while len(inflight) < args.workers and next_i < len(chosen) and not escalated:
            scene = chosen[next_i]
            inflight[pool.submit(run_one, scene)] = next_i
            next_i += 1

    discard_from = None
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        submit_more(pool)
        while inflight:
            done, _pending = wait(set(inflight), return_when=FIRST_COMPLETED)
            for future in done:
                index = inflight.pop(future)
                completed[index] = future.result()
            while next_take in completed and discard_from is None:
                row = completed.pop(next_take)
                print(json.dumps({
                    "entry_id": row["entry_id"],
                    "status": row["status"],
                    "attempts": row["attempts"],
                    **({"reason": row["reason"]} if row["status"] == "HOLD" else {"out": row["out"]}),
                }), flush=True)
                if row["status"] == "HOLD":
                    holds.append(row)
                    streak += 1
                    if streak >= 3:
                        escalated = True
                        discard_from = next_take + 1
                        break
                else:
                    scenes.append(row)
                    streak = 0
                next_take += 1
            if escalated:
                break
            submit_more(pool)

    if escalated:
        for index in range(discard_from or next_take, len(chosen)):
            scene = chosen[index]
            if index in completed:
                row = completed[index]
                if row["status"] != "HOLD":
                    revert_motion(scene)
                else:
                    sa.hold(scene, row.get("reason") or "discarded after escalate")
            else:
                revert_motion(scene)
            not_attempted.append(scene["entry_id"])
        # In-flight workers may still be writing. Wait, then revert anything
        # they shipped past the stop.
        if inflight:
            wait(set(inflight))
            for future, index in list(inflight.items()):
                if index < (discard_from or 0):
                    continue
                try:
                    row = future.result()
                except Exception:
                    row = None
                revert_motion(chosen[index])
                if row and row["status"] == "HOLD":
                    sa.hold(chosen[index], row.get("reason") or "")
                if chosen[index]["entry_id"] not in not_attempted:
                    not_attempted.append(chosen[index]["entry_id"])

    scenes.sort(key=lambda row: row["entry_id"])
    holds.sort(key=lambda row: row["entry_id"])
    write_evidence(scenes, holds, not_attempted, prior_hold_rows, night, manifests, escalated)
    remaining = sa.remaining_daylight(manifests)
    print(
        f"wrote {EVIDENCE_PATH} clips={len(scenes)} holds={len(holds)} "
        f"escalated={escalated} not_attempted={len(not_attempted)} "
        f"remaining={len(remaining)}"
    )
    if escalated:
        raise SystemExit("ESCALATE: 3 holds in a row")


if __name__ == "__main__":
    main()
