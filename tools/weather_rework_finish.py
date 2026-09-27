#!/usr/bin/env python3
"""Re-finish GR-01-001–087 after a per-scene Open-Meteo retrieval.

The photograph is the existing master with the baked caption band inpainted.
It is not a new composition: a trial regeneration of GR-01-008 put heads back
on the Lion Gate relief, which Cosmo already rejected. Fresh model values
match the sky those masters were checked against (one temperature sign on
GR-01-016). The finish is the label bar: 1920×1270, 864×1270, 1080×2110,
190px #0e0e12, curly Jason D’s Vision, Allura Jason A. Devlin.

Status stays Candidate. This script does not approve anything.
"""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WEATHER = Path("/tmp/gr_weather_001_087.json")
SANS = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
SANS_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
ALLURA = Path(__file__).resolve().parent / "fonts" / "Allura-Regular.ttf"

BRAND = "Jason D\u2019s Vision"
SIGNATURE_NAME = "Jason A. Devlin"
DISCLOSURE = "AI-generated artistic interpretation \u00b7 Not a photograph."

BAR_H = 190
HAIRLINE = 2
BAR_BG = (0x0E, 0x0E, 0x12)
HAIR = (0xE4, 0xE4, 0xEA)
INK = (255, 255, 255)
INK_SCENARIO = (214, 214, 222)
INK_DISCLOSURE = (176, 176, 186)

PHOTO = {"16x9": (1920, 1080), "4x5": (864, 1080), "9x16": (1080, 1920)}
CANVAS = {"16x9": (1920, 1270), "4x5": (864, 1270), "9x16": (1080, 2110)}
PNG_SIG = b"\x89PNG\r\n\x1a\n"

TITLE = "Jason D's Vision \u2014 AI-generated artistic interpretation"
DESCRIPTION = (
    "AI-generated artistic interpretation from the Jason D's Vision Greece gallery. "
    "Created with generative AI; not a photograph."
)
COPYRIGHT = "Jason D's Vision \u2014 AI-generated content"
SOFTWARE = "Jason D's Vision library pipeline"
COMMENT = (
    "EU AI Act Art. 50 transparency note: this image is AI-generated content. "
    "Machine-readable disclosure embedded 2026-09-26."
)
ART50_KEYS = ("Title", "Description", "Copyright", "Software", "Comment")

WMO = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _chunk(ctype: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)


def _text_chunk(key: str, value: str) -> bytes:
    return _chunk(b"tEXt", key.encode("latin-1") + b"\x00" + value.encode("latin-1"))


def _itxt_chunk(key: str, value: str) -> bytes:
    data = (
        key.encode("latin-1")
        + b"\x00\x00\x00\x00\x00"
        + value.encode("utf-8")
    )
    return _chunk(b"iTXt", data)


def art50_chunks() -> list[bytes]:
    return [
        _itxt_chunk("Title", TITLE),
        _text_chunk("Description", DESCRIPTION),
        _itxt_chunk("Copyright", COPYRIGHT),
        _text_chunk("Software", SOFTWARE),
        _text_chunk("Comment", COMMENT),
    ]


def inject_art50(path: Path) -> None:
    data = path.read_bytes()
    if data[:8] != PNG_SIG:
        raise SystemExit(f"not a png: {path}")
    out = [data[:8]]
    i = 8
    inserted = False
    while i + 12 <= len(data):
        length = struct.unpack(">I", data[i : i + 4])[0]
        ctype = data[i + 4 : i + 8]
        end = i + 12 + length
        payload = data[i + 8 : i + 8 + length]
        if ctype in (b"tEXt", b"iTXt", b"zTXt"):
            key = payload.split(b"\x00", 1)[0].decode("latin-1")
            if key in ART50_KEYS:
                i = end
                continue
        if ctype == b"IEND":
            out.extend(art50_chunks())
            out.append(data[i:end])
            inserted = True
            i = end
            break
        out.append(data[i:end])
        i = end
    if not inserted:
        raise SystemExit(f"IEND missing: {path}")
    path.write_bytes(b"".join(out))


def text_band(arr: np.ndarray) -> tuple[np.ndarray, int, int, int]:
    """Mask the baked caption cluster at the bottom. Returns mask, y0, y1, count."""
    height, width = arr.shape[:2]
    maximum = arr.max(axis=2)
    minimum = arr.min(axis=2)
    white = (maximum > 168) & ((maximum.astype(np.int16) - minimum.astype(np.int16)) < 58)
    counts = white.sum(axis=1)
    thresh = max(8, int(width * 0.008))
    floor = int(height * 0.78)
    y = height - 1
    while y > floor and counts[y] < 6:
        y -= 1
    y1 = y
    y0 = y
    gap = 0
    while y > floor:
        if counts[y] >= thresh:
            y0 = y
            gap = 0
        else:
            gap += 1
            if gap >= 16 and (y1 - y0) > 18:
                break
        y -= 1
    y0 = max(floor, y0 - 4)
    y1 = min(height - 1, y1 + 6)
    mask = np.zeros((height, width), dtype=bool)
    mask[y0 : y1 + 1] = white[y0 : y1 + 1]
    pil = Image.fromarray((mask * 255).astype(np.uint8), "L")
    dilated = np.asarray(pil.filter(ImageFilter.MaxFilter(5))) > 0
    # Keep the dilation inside the band so bright stone above the caption stays.
    dilated[:y0] = False
    return dilated, y0, y1, int(mask.sum())


def inpaint(image: np.ndarray, hole: np.ndarray) -> np.ndarray:
    acc = image.astype(np.float32)
    filled = ~hole
    remain = hole.copy()
    height, width = hole.shape
    shifts = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1))
    for _ in range(48):
        if not remain.any():
            break
        total = np.zeros_like(acc)
        count = np.zeros((height, width), np.float32)
        for dy, dx in shifts:
            ys = slice(max(0, -dy), height - max(0, dy))
            xs = slice(max(0, -dx), width - max(0, dx))
            ysrc = slice(max(0, dy), height - max(0, -dy))
            xsrc = slice(max(0, dx), width - max(0, -dx))
            known = np.zeros((height, width), dtype=bool)
            known[ys, xs] = filled[ysrc, xsrc]
            vals = np.zeros_like(acc)
            vals[ys, xs] = acc[ysrc, xsrc]
            total += vals * known[..., None]
            count += known
        newly = remain & (count > 0)
        if not newly.any():
            break
        acc[newly] = total[newly] / count[newly, None]
        filled[newly] = True
        remain[newly] = False
    if remain.any():
        raise SystemExit(f"inpaint left {int(remain.sum())} pixels")
    return np.clip(np.rint(acc), 0, 255).astype(np.uint8)


def clean_photo(path: Path) -> tuple[Image.Image, dict]:
    image = Image.open(path).convert("RGB")
    arr = np.asarray(image)
    if image.size not in ((1920, 1080), (864, 1080)):
        raise SystemExit(f"unexpected size {path} {image.size}")
    mask, y0, y1, count = text_band(arr)
    cleaned = inpaint(arr, mask)
    # Rows above the caption band are copied, not estimated.
    cleaned[:y0] = arr[:y0]
    stats = {"y0": y0, "y1": y1, "text_pixels": count, "inpaint": int(mask.sum())}
    return Image.fromarray(cleaned, "RGB"), stats


def fit(im: Image.Image, tw: int, th: int) -> Image.Image:
    im = im.convert("RGB")
    width, height = im.size
    target = tw / th
    current = width / height
    if abs(current - target) > 1e-6:
        if current > target:
            new_w = int(round(height * target))
            left = (width - new_w) // 2
            im = im.crop((left, 0, left + new_w, height))
        else:
            new_h = int(round(width / target))
            top = max(0, (height - new_h) // 2)
            im = im.crop((0, top, width, top + new_h))
    if im.size != (tw, th):
        im = im.resize((tw, th), Image.Resampling.LANCZOS)
    return im


def _bbox(font: ImageFont.FreeTypeFont, text: str) -> tuple[int, int, int, int]:
    return font.getbbox(text, anchor="lt")


def _measure(font: ImageFont.FreeTypeFont, text: str) -> tuple[int, int]:
    left, top, right, bottom = _bbox(font, text)
    return right - left, bottom - top


def _fonts(scale: float) -> dict[str, ImageFont.FreeTypeFont]:
    def px(size: float, floor: int) -> int:
        return max(floor, int(round(size * scale)))

    return {
        "cap": ImageFont.truetype(str(SANS_BOLD), px(28, 15)),
        "sc": ImageFont.truetype(str(SANS), px(18, 12)),
        "disc": ImageFont.truetype(str(SANS), px(16, 11)),
        "brand": ImageFont.truetype(str(SANS), px(20, 13)),
        "name": ImageFont.truetype(str(ALLURA), px(46, 28)),
    }


def _stack_size(lines: list[tuple[str, ImageFont.FreeTypeFont]], gap: int) -> tuple[int, int]:
    width = 0
    height = 0
    for index, (text, font) in enumerate(lines):
        text_w, text_h = _measure(font, text)
        width = max(width, text_w)
        height += text_h
        if index:
            height += gap
    return width, height


def layout_fonts(width: int, caption: str, scenario: str):
    scale = 1.0 if width >= 1600 else (0.9 if width >= 1000 else 0.78)
    for _ in range(18):
        fonts = _fonts(scale)
        gap = max(4, int(round(6 * scale)))
        margin = max(20, int(round(width * 0.028)))
        col_gap = max(16, int(round(width * 0.018)))
        left_w, left_h = _stack_size(
            [(caption, fonts["cap"]), (scenario, fonts["sc"]), (DISCLOSURE, fonts["disc"])],
            gap,
        )
        right_w, right_h = _stack_size(
            [(BRAND, fonts["brand"]), (SIGNATURE_NAME, fonts["name"])],
            gap,
        )
        content_h = BAR_H - HAIRLINE
        if (
            margin * 2 + col_gap + left_w + right_w <= width
            and left_h <= content_h - 16
            and right_h <= content_h - 12
        ):
            return fonts, gap
        scale *= 0.94
    raise SystemExit(f"label text does not fit a {width}px bar for {caption!r}")


def draw_label_bar(photo: Image.Image, caption: str, scenario_label: str) -> Image.Image:
    photo = photo.convert("RGB")
    pw, ph = photo.size
    canvas = Image.new("RGB", (pw, ph + BAR_H), BAR_BG)
    canvas.paste(photo, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, ph, pw - 1, ph + HAIRLINE - 1), fill=HAIR)
    fonts, gap = layout_fonts(pw, caption, f"Scenario: {scenario_label}")
    margin = max(20, int(round(pw * 0.028)))
    scenario = f"Scenario: {scenario_label}"
    left = [
        (caption, fonts["cap"], INK),
        (scenario, fonts["sc"], INK_SCENARIO),
        (DISCLOSURE, fonts["disc"], INK_DISCLOSURE),
    ]
    right = [
        (BRAND, fonts["brand"], INK),
        (SIGNATURE_NAME, fonts["name"], INK),
    ]

    def stack_height(rows):
        total = 0
        for index, (text, font, _ink) in enumerate(rows):
            total += _measure(font, text)[1]
            if index:
                total += gap
        return total

    def stack_width(rows):
        return max(_measure(font, text)[0] for text, font, _ink in rows)

    content_top = ph + HAIRLINE
    content_h = BAR_H - HAIRLINE

    def draw_stack(rows, align: str) -> None:
        block_h = stack_height(rows)
        block_w = stack_width(rows)
        y = content_top + max(0, (content_h - block_h) // 2)
        for text, font, ink in rows:
            text_w, text_h = _measure(font, text)
            left_edge, top_edge, _right, _bottom = _bbox(font, text)
            x = margin if align == "left" else pw - margin - block_w + (block_w - text_w)
            draw.text((x - left_edge, y - top_edge), text, font=font, fill=ink)
            y += text_h + gap

    draw_stack(left, "left")
    draw_stack(right, "right")
    return canvas


def save_master(im: Image.Image, path: Path, photo: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, format="PNG", compress_level=9)
    inject_art50(path)
    with Image.open(path) as saved:
        saved.load()
        if saved.size != im.size:
            raise SystemExit(f"bad size {path} {saved.size}")
        top = saved.crop((0, 0, photo.width, photo.height)).convert("RGB")
        top_arr = np.asarray(top)
        photo_arr = np.asarray(photo)
        if top_arr.shape != photo_arr.shape or np.any(top_arr != photo_arr):
            raise SystemExit(f"photo pixels were altered: {path}")
        if saved.getpixel((2, saved.height - 1))[:3] != BAR_BG:
            raise SystemExit(f"label bar background {path}")
        if saved.getpixel((2, photo.height))[:3] != HAIR:
            raise SystemExit(f"hairline missing {path}")


def athens_retrieval(ts: str) -> str:
    # EEST is UTC+3 on 27 September 2026.
    stamp = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    local = stamp.replace(hour=(stamp.hour + 3) % 24)
    # The fetches in this batch are all 16:53–16:54Z, so the Athens date does not roll.
    return local.strftime("%-d %B %Y %H:%M:%S") if False else _fmt_local(stamp)


def _fmt_local(stamp: datetime) -> str:
    local = stamp.replace(hour=stamp.hour + 3)
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    return (
        f"{local.day} {months[local.month - 1]} {local.year} "
        f"{local.hour:02d}:{local.minute:02d}:{local.second:02d}"
    )


def weather_sentence(row: dict) -> str:
    valid = datetime.strptime(row["valid_local"], "%Y-%m-%dT%H:%M")
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    valid_s = (
        f"{valid.day} {months[valid.month - 1]} {valid.year} "
        f"{valid.hour:02d}:{valid.minute:02d} Europe/Athens"
    )
    hour = int(row["scenario_hm"][:2])
    code = int(row["code"])
    name = WMO.get(code, f"code {code}")
    temp = row["temp"]
    temp_s = f"{temp:.1f}"
    wind = row["wind"]
    wind_s = f"{wind:.1f}"
    precip = row["precip"]
    snow = row["snow"]
    return (
        f"Model data from Open-Meteo, retrieved {row['retrieved']}, "
        f"{_fmt_local(datetime.strptime(row['retrieved'], '%Y-%m-%dT%H:%M:%SZ'))} Europe/Athens, "
        f"HTTP Date {row['http_date']}, valid {valid_s} — not a verified on-site observation. "
        f"Separate request for {row['lat']}, {row['lon']}. "
        f"The model-valid hour is {hour:02d}:00–{hour:02d}:59 Europe/Athens. "
        f"The cited model time is the {valid.hour:02d}:{valid.minute:02d} step "
        f"(interval 900 seconds, minutely_15 index {row['index']}). "
        f"The scenario minute {row['scenario_hm']} Europe/Athens falls inside that model-valid hour. "
        f"Weather code {code} ({name}), cloud cover {int(row['cloud'])}%, {temp_s}°C, "
        f"wind {wind_s} km/h, relative humidity {int(row['rh'])}%, "
        f"precipitation {precip:.1f} mm, is_day {int(row['is_day'])}, snowfall {snow:.1f} cm. "
        f"Model cell about {row['cell_lat']}, {row['cell_lon']}, elevation about {row['elevation']:.0f} m."
    )


def replace_weather_line(text: str, sentence: str) -> str:
    lines = text.splitlines()
    found = False
    for index, line in enumerate(lines):
        if line.startswith("- Weather:"):
            lines[index] = "- Weather: " + sentence
            found = True
            break
    if not found:
        raise SystemExit("weather bullet missing")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def append_rework(text: str, row: dict) -> str:
    marker = "## Weather rework 2026-09-27"
    if marker in text:
        text = text.split(marker)[0].rstrip() + "\n"
    block = f"""
{marker}
Per-scene Open-Meteo forecast HTTP fetch, retrieval {row['retrieved']} (HTTP Date {row['http_date']}). The scenario minute {row['scenario_hm']} sits inside the {row['scenario_hm'][:2]}:00–{row['scenario_hm'][:2]}:59 model-valid hour. Depicted sky is the prior master: this pass did not generate a new composition, because a trial regeneration changed Gate-1 geometry. Baked caption type was lifted off the photo and the finish bar was added underneath.
Masters: 16:9 1920×1270, 4:5 864×1270, 9:16 1080×2110. The bar is 190px #0e0e12 under the photo, with a 2px hairline. Signature is Jason D’s Vision (curly apostrophe) and Jason A. Devlin in Allura.
approval_status stays Candidate. This note does not approve the scene.
"""
    return text.rstrip() + "\n" + block


def update_manifest(row: dict, hashes: dict[str, str], stats: dict) -> None:
    path = ROOT / "manifests" / f"{row['entry_id']}.json"
    data = json.loads(path.read_text())
    if data.get("entry_id") != row["entry_id"]:
        raise SystemExit("entry mismatch")
    rel16 = row["file_16x9"]
    rel9 = str(Path(rel16).with_name(Path(rel16).name.replace("-16x9.png", "-9x16.png")))
    data["file_9x16"] = rel9
    data["approval_status"] = "Candidate"
    data.pop("approved_at", None)
    data["qc_status"] = "Candidate — weather rework re-finish 2026-09-27, awaiting Cosmo QC"
    data["sha256_16x9"] = hashes["16x9"]
    data["sha256_4x5"] = hashes["4x5"]
    data["sha256_9x16"] = hashes["9x16"]
    hour = row["scenario_hm"][:2]
    code = int(row["code"])
    data["weather"] = {
        "provider": "Open-Meteo",
        "retrieval_timestamp": row["retrieved"],
        "http_date": row["http_date"],
        "valid_local": row["valid_local"],
        "timezone": "Europe/Athens",
        "model_valid_hour": f"{hour}:00-{hour}:59",
        "scenario_minute": row["scenario_hm"],
        "latitude": row["lat"],
        "longitude": row["lon"],
        "model_cell_latitude": row["cell_lat"],
        "model_cell_longitude": row["cell_lon"],
        "elevation_m": row["elevation"],
        "minutely_15_index": row["index"],
        "weather_code": code,
        "weather_code_name": WMO.get(code, f"code {code}"),
        "cloud_cover_percent": int(row["cloud"]),
        "temperature_c": row["temp"],
        "wind_kmh": row["wind"],
        "relative_humidity_percent": int(row["rh"]),
        "precipitation_mm": row["precip"],
        "is_day": int(row["is_day"]),
        "snowfall_cm": row["snow"],
        "wording": "Model data from Open-Meteo, retrieved "
        + row["retrieved"]
        + ", valid "
        + row["valid_local"]
        + " Europe/Athens — not a verified on-site observation.",
    }
    data["approval_basis"] = (
        f"Candidate only. Weather rework 2026-09-27: own Open-Meteo HTTP fetch "
        f"{row['retrieved']} ({row['http_date']}), separate request for {row['lat']}, {row['lon']}, "
        f"valid {row['valid_local']} Europe/Athens, scenario {row['scenario_hm']} inside "
        f"{hour}:00–{hour}:59. Code {code} ({WMO.get(code, code)}), cloud {int(row['cloud'])}%, "
        f"{row['temp']:.1f}°C, wind {row['wind']:.1f} km/h, precipitation {row['precip']:.1f} mm, "
        f"is_day {int(row['is_day'])}. Finish 1920×1270 / 864×1270 / 1080×2110, 190px #0e0e12 bar, "
        f"curly Jason D’s Vision and Allura Jason A. Devlin. Photo is the prior master with baked "
        f"type removed (caption band y {stats['16x9']['y0']}–{stats['16x9']['y1']} on 16:9); "
        f"not a new composition. Not approved."
    )
    notes = data.get("qc_notes") or []
    notes.append(
        {
            "at": "2026-09-27T16:55:00Z",
            "by": "builder",
            "note": (
                f"Weather rework recorded. Per-scene Open-Meteo retrieval {row['retrieved']} "
                f"unique to the second; scenario {row['scenario_hm']} inside the model-valid hour; "
                f"code {code}, cloud {int(row['cloud'])}%. Masters re-finished to 1920×1270 / "
                f"864×1270 / 1080×2110 with the 190px label bar. Still Candidate. Not an approval."
            ),
        }
    )
    data["qc_notes"] = notes
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def finish_one(row: dict, write: bool) -> dict:
    src16 = ROOT / row["file_16x9"]
    src45 = ROOT / row["file_4x5"]
    photo16, st16 = clean_photo(src16)
    photo45, st45 = clean_photo(src45)
    if photo16.size != PHOTO["16x9"] or photo45.size != PHOTO["4x5"]:
        raise SystemExit(f"{row['entry_id']} cleaned size {photo16.size} {photo45.size}")
    photo916 = fit(photo16, *PHOTO["9x16"])
    masters = {
        "16x9": draw_label_bar(photo16, row["caption"], row["scenario_label"]),
        "4x5": draw_label_bar(photo45, row["caption"], row["scenario_label"]),
        "9x16": draw_label_bar(photo916, row["caption"], row["scenario_label"]),
    }
    for fmt, im in masters.items():
        if im.size != CANVAS[fmt]:
            raise SystemExit(f"{row['entry_id']} {fmt} {im.size}")
    rel9 = str(Path(row["file_16x9"]).with_name(Path(row["file_16x9"]).name.replace("-16x9.png", "-9x16.png")))
    outs = {
        "16x9": ROOT / row["file_16x9"],
        "4x5": ROOT / row["file_4x5"],
        "9x16": ROOT / rel9,
    }
    photos = {"16x9": photo16, "4x5": photo45, "9x16": photo916}
    if write:
        for fmt in ("16x9", "4x5", "9x16"):
            save_master(masters[fmt], outs[fmt], photos[fmt])
        note = ROOT / "approvals" / f"{row['entry_id']}.md"
        text = note.read_text()
        text = replace_weather_line(text, weather_sentence(row))
        text = append_rework(text, row)
        # The page status line already says Candidate on these notes; keep it that way.
        text = text.replace(
            "approval_status on the page: Approved",
            "approval_status on the page: Candidate",
        )
        note.write_text(text)
        update_manifest(row, {fmt: sha256_file(outs[fmt]) for fmt in outs}, {"16x9": st16, "4x5": st45})
    return {"16x9": st16, "4x5": st45, "paths": {k: str(v) for k, v in outs.items()}}


def main() -> None:
    rows = json.loads(WEATHER.read_text())
    if len(rows) != 87:
        raise SystemExit(f"expected 87 weather rows, got {len(rows)}")
    stamps = [row["retrieved"] for row in rows]
    if len(set(stamps)) != 87:
        raise SystemExit("retrieval timestamps are not unique inside the batch")
    problems = []
    for row in rows:
        stats = finish_one(row, write=True)
        for fmt, st in (("16x9", stats["16x9"]), ("4x5", stats["4x5"])):
            if st["text_pixels"] < 200:
                problems.append(f"{row['entry_id']} {fmt} thin text mask {st['text_pixels']} y {st['y0']}-{st['y1']}")
            if st["y0"] < 900 and fmt == "16x9":
                problems.append(f"{row['entry_id']} 16x9 caption band starts high y {st['y0']}")
        print(f"{row['entry_id']} {row['retrieved']} band16 {stats['16x9']['y0']}-{stats['16x9']['y1']} px {stats['16x9']['text_pixels']}", flush=True)
    if problems:
        print("PROBLEMS")
        for line in problems:
            print(line)
    else:
        print("no band problems")


if __name__ == "__main__":
    main()
