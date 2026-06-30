"""Generates looper.ico — run once as part of the installer build."""
import math
import os
from PIL import Image, ImageDraw, ImageFont


def _font(size):
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
        r"C:\Windows\Fonts\verdanab.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _frame(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background rounded square — deep violet
    pad = max(1, size // 14)
    r = size // 4
    draw.rounded_rectangle(
        [pad, pad, size - 1 - pad, size - 1 - pad],
        radius=r,
        fill=(76, 29, 149, 255),   # violet-900
    )
    # Slightly lighter inner face (depth)
    pad2 = pad + max(1, size // 22)
    draw.rounded_rectangle(
        [pad2, pad2, size - 1 - pad2, size - 1 - pad2],
        radius=max(2, r - 3),
        fill=(109, 40, 217, 255),  # violet-700
    )

    cx, cy = size / 2, size / 2

    # Circular arrow — white arc (300 degrees) + arrowhead
    arc_r = size * 0.30
    arc_w = max(2, size // 9)
    bbox = [cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r]

    # Arc from 120° to 60° going clockwise (300° sweep, gap at top-right)
    start_deg, end_deg = 120, 60
    draw.arc(bbox, start=start_deg, end=end_deg, fill=(255, 255, 255, 255), width=arc_w)

    # Arrowhead at end_deg (60°)
    tip_rad = math.radians(end_deg)
    tx = cx + arc_r * math.cos(tip_rad)
    ty = cy + arc_r * math.sin(tip_rad)
    tangent = tip_rad + math.pi / 2   # clockwise tangent
    arrow_len = max(3, size // 7)
    spread = math.pi * 0.38
    p1 = (tx + arrow_len * math.cos(tangent - spread),
          ty + arrow_len * math.sin(tangent - spread))
    p2 = (tx + arrow_len * math.cos(tangent + spread),
          ty + arrow_len * math.sin(tangent + spread))
    draw.polygon([( tx, ty), p1, p2], fill=(255, 255, 255, 255))

    # Small "L" in centre
    fs = max(6, int(size * 0.22))
    font = _font(fs)
    bbox_t = draw.textbbox((0, 0), "L", font=font)
    tw, th = bbox_t[2] - bbox_t[0], bbox_t[3] - bbox_t[1]
    draw.text(
        (cx - tw / 2 - bbox_t[0], cy - th / 2 - bbox_t[1]),
        "L",
        fill=(255, 255, 255, 200),
        font=font,
    )

    return img


def main(out_path="assets/looper.ico"):
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [_frame(s) for s in sizes]
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    frames[0].save(
        out_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f"Icon written: {out_path}")


if __name__ == "__main__":
    main()
