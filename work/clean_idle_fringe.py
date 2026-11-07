"""Conservative cleanup of exterior-connected white cutout fringe.

Uses one canonical mask and never crops or resizes. Alpha is preserved by default;
the optional bounded white-edge trim must be shared by all animation frames.
Candidates require independent visual review before use.
"""
from __future__ import annotations

import argparse
from array import array
from collections import deque
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw


def neighbors4(i, w, h):
    x, y = i % w, i // w
    if x:
        yield i - 1
    if x + 1 < w:
        yield i + 1
    if y:
        yield i - w
    if y + 1 < h:
        yield i + w


def composite(im, color):
    bg = Image.new("RGBA", im.size, color)
    bg.alpha_composite(im)
    return bg.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--depth", type=int, default=4)
    ap.add_argument("--white-min", type=int, default=224)
    ap.add_argument("--white-spread", type=int, default=35)
    ap.add_argument("--trim-white-depth", type=int, default=0, help="Optional bounded alpha trim of selected exterior white pixels; default preserves alpha.")
    args = ap.parse_args()
    if not 0 <= args.trim_white_depth <= 4:
        ap.error("White-edge alpha trim is limited to 0..4 source pixels.")
    if not 1 <= args.depth <= 16:
        ap.error("Inward selection depth must be within the 1..16 pixel distance map.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    original_bytes = args.input.read_bytes()
    im = Image.open(args.input).convert("RGBA")
    w, h = im.size
    pixels = list(im.get_flattened_data())
    n = w * h
    alpha = bytearray(p[3] for p in pixels)

    # Only transparent pixels connected to the canvas exterior seed the band.
    exterior = bytearray(n)
    q = deque()
    for i in list(range(w)) + list(range((h - 1) * w, h * w)):
        if alpha[i] <= 8 and not exterior[i]:
            exterior[i] = 1
            q.append(i)
    for y in range(h):
        for i in (y * w, y * w + w - 1):
            if alpha[i] <= 8 and not exterior[i]:
                exterior[i] = 1
                q.append(i)
    while q:
        i = q.popleft()
        for j in neighbors4(i, w, h):
            if alpha[j] <= 8 and not exterior[j]:
                exterior[j] = 1
                q.append(j)

    distance = array("H", [65535]) * n
    q = deque()
    for i, flag in enumerate(exterior):
        if flag:
            distance[i] = 0
            # Boundary pixels only are enough to start the inward distance map.
            if any(not exterior[j] for j in neighbors4(i, w, h)):
                q.append(i)
    while q:
        i = q.popleft()
        if distance[i] >= 16:
            continue
        for j in neighbors4(i, w, h):
            if distance[j] > distance[i] + 1:
                distance[j] = distance[i] + 1
                q.append(j)

    near_white = bytearray(n)
    for i, (r, g, b, a) in enumerate(pixels):
        if a and distance[i] <= args.depth:
            near_white[i] = min(r, g, b) >= args.white_min and max(r, g, b) - min(r, g, b) <= args.white_spread

    # Require a near-white path to the outside, not merely proximity to it.
    selected = bytearray(n)
    q = deque()
    for i, flag in enumerate(near_white):
        if flag and (exterior[i] or any(exterior[j] for j in neighbors4(i, w, h))):
            selected[i] = 1
            q.append(i)
    while q:
        i = q.popleft()
        for j in neighbors4(i, w, h):
            if near_white[j] and not selected[j]:
                selected[j] = 1
                q.append(j)

    offsets = sorted((dx * dx + dy * dy, dx, dy) for dy in range(-12, 13) for dx in range(-12, 13) if 0 < dx * dx + dy * dy <= 144)
    result = pixels[:]
    changed = bytearray(n)
    no_donor = 0
    for i, flag in enumerate(selected):
        if not flag:
            continue
        if args.trim_white_depth and distance[i] <= args.trim_white_depth:
            result[i] = (0, 0, 0, 0)
            changed[i] = 255
            continue
        x, y = i % w, i // w
        donor = None
        for _, dx, dy in offsets:
            xx, yy = x + dx, y + dy
            if not (0 <= xx < w and 0 <= yy < h):
                continue
            j = yy * w + xx
            r, g, b, a = pixels[j]
            if a >= 230 and not selected[j] and distance[j] > distance[i] and max(r, g, b) <= 220 and min(r, g, b) < 190:
                donor = (r, g, b, pixels[i][3])
                break
        if donor is None:
            no_donor += 1
            continue
        if donor != pixels[i]:
            result[i] = donor
            changed[i] = 255
    cleaned = Image.new("RGBA", im.size)
    cleaned.putdata(result)
    alpha_unchanged = cleaned.getchannel("A").tobytes() == im.getchannel("A").tobytes()
    if not args.trim_white_depth:
        assert alpha_unchanged
    output_path = args.output_dir / "canonical-edge-cleaned.png"
    cleaned.save(output_path)
    mask = Image.frombytes("L", im.size, bytes(changed))
    mask.save(args.output_dir / "shared-rgb-mask.png")
    cleaned.getchannel("A").save(args.output_dir / "shared-alpha-mask.png")

    # Normal pet size plus enlarged top/hair and leg crops, on dark and light.
    canvas = Image.new("RGB", (1100, 1210), "#e4e8ed")
    draw = ImageDraw.Draw(canvas)
    draw.text((16, 8), f"Canvas unchanged; alpha trim depth {args.trim_white_depth}px. BEFORE left, AFTER right.", fill="black")
    for col, source in enumerate((im, cleaned)):
        x = 10 + col * 550
        for row, bg in enumerate(("#181b22", "#ffffff")):
            full = composite(source, bg).resize((440, 440), Image.Resampling.LANCZOS)
            canvas.paste(full, (x, 35 + row * 450))
            normal = composite(source.resize((192, 192), Image.Resampling.LANCZOS), bg)
            canvas.paste(normal, (x + 345, 35 + row * 450 + 245))
        draw.text((x, 940), "Top/hair crop at 2x", fill="black")
        crop = composite(source, "#181b22").crop((330, 65, 600, 150)).resize((540, 170), Image.Resampling.NEAREST)
        canvas.paste(crop, (x, 960))
        draw.text((x, 1138), "192x208 placement is parent-owned; no fitting or geometry change here.", fill="black")
    canvas.save(args.output_dir / "before-after.png")
    report = {
        "source": str(args.input.resolve()),
        "source_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "candidate": str(output_path.resolve()),
        "size": [w, h],
        "method": "exterior-connected near-white RGB recolor from nearby darker inward donor",
        "settings": {"max_inward_depth_px": args.depth, "minimum_rgb": args.white_min, "max_channel_spread": args.white_spread, "exterior_alpha_max": 8, "donor_radius": 12, "trim_white_depth": args.trim_white_depth},
        "selected_pixels": sum(selected),
        "changed_pixels": sum(bool(v) for v in changed),
        "changed_visible_alpha_gt16": sum(bool(changed[i]) and alpha[i] > 16 for i in range(n)),
        "selected_without_donor": no_donor,
        "change_bbox": mask.getbbox(),
        "alpha_unchanged": alpha_unchanged,
        "alpha_changed_pixels": sum(result[i][3] != alpha[i] for i in range(n)),
        "alpha_mass_removed_fraction": (sum(alpha) - sum(p[3] for p in result)) / sum(alpha),
        "source_alpha_bbox": im.getchannel("A").getbbox(),
        "candidate_alpha_bbox": cleaned.getchannel("A").getbbox(),
        "canvas_unchanged": True,
        "source_file_unchanged": args.input.read_bytes() == original_bytes,
        "unselected_rgb_unchanged": all(selected[i] or result[i] == pixels[i] for i in range(n)),
        "risks": [f"May darken true pale highlights where they touch the outer boundary within {args.depth} pixels.", "Optional alpha trim contracts only selected near-white exterior fringe; all frames must share this alpha mask.", "Nearest inward donor can make some narrow outlines darker; inspect at normal pet size before adoption."],
    }
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
