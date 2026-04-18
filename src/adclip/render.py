"""Render pipeline: takes a compose plan + raw visual -> finished ad file."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _draw_text_overlay(draw: ImageDraw.ImageDraw, overlay: dict, img_w: int, img_h: int) -> None:
    text = overlay["text"]
    pad = overlay.get("pad", 48)
    font_size = overlay.get("font_size", 48)
    color = _hex_to_rgb(overlay.get("color", "#ffffff"))
    stroke_color = _hex_to_rgb(overlay.get("stroke", "#000000"))
    pos = overlay.get("position", "top")

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except (IOError, OSError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except (IOError, OSError):
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    x = (img_w - text_w) // 2

    if pos == "top":
        y = pad
    elif pos == "bottom":
        y = img_h - text_h - pad
    else:
        y = (img_h - text_h) // 2

    draw.text(
        (x, y), text, font=font, fill=color,
        stroke_width=4, stroke_fill=stroke_color,
    )


def render_static_ad(plan: dict, *, background: str, output: str) -> None:
    if plan["kind"] != "static":
        raise ValueError(f"render_static_ad called on non-static plan: {plan['kind']}")

    img = Image.open(background).convert("RGB")
    draw = ImageDraw.Draw(img)

    for ov in plan["overlays"]:
        if ov["type"] == "text":
            _draw_text_overlay(draw, ov, img.width, img.height)
        # image overlays left for a later task -- not needed for minimal v0.1

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    img.save(output)
