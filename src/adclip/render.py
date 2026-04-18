"""Render pipeline: takes a compose plan + raw visual -> finished ad file."""

from __future__ import annotations

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


def _paste_image_overlay(base: Image.Image, overlay: dict) -> None:
    src = Image.open(overlay["path"]).convert("RGBA")

    max_w = overlay.get("max_width")
    if max_w and src.width > max_w:
        ratio = max_w / src.width
        new_size = (max_w, max(1, int(src.height * ratio)))
        src = src.resize(new_size, Image.Resampling.LANCZOS)

    pad = overlay.get("pad", 32)
    pos = overlay.get("position", "bottom_right")
    bw, bh = base.size
    sw, sh = src.size

    if pos == "top_left":
        xy = (pad, pad)
    elif pos == "top_right":
        xy = (bw - sw - pad, pad)
    elif pos == "bottom_left":
        xy = (pad, bh - sh - pad)
    elif pos == "center":
        xy = ((bw - sw) // 2, (bh - sh) // 2)
    else:  # bottom_right (default)
        xy = (bw - sw - pad, bh - sh - pad)

    base.paste(src, xy, mask=src)


def render_static_ad(plan: dict, *, background: str, output: str) -> None:
    if plan["kind"] != "static":
        raise ValueError(f"render_static_ad called on non-static plan: {plan['kind']}")

    img = Image.open(background).convert("RGBA")

    for ov in plan["overlays"]:
        if ov["type"] == "image":
            _paste_image_overlay(img, ov)

    draw = ImageDraw.Draw(img)
    for ov in plan["overlays"]:
        if ov["type"] == "text":
            _draw_text_overlay(draw, ov, img.width, img.height)

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(output)
