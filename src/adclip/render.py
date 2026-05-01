"""Render pipeline: takes a compose plan + raw visual -> finished ad file."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _draw_text_overlay(draw: ImageDraw.ImageDraw, overlay: dict, img_w: int, img_h: int) -> None:
    text = overlay.get("text") or ""
    if not text:
        return
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
    path = overlay.get("path")
    if not path:
        return
    try:
        src = Image.open(path).convert("RGBA")
    except (FileNotFoundError, OSError):
        return

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


def has_drawtext() -> bool:
    """Whether the system ffmpeg was compiled with the drawtext filter."""
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        return False
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return any(
        line.split()[1:2] == ["drawtext"]
        for line in proc.stdout.splitlines()
        if line.strip()
    )


def _has_audio(path: str) -> bool:
    try:
        import av

        container = av.open(path)
        try:
            return len(container.streams.audio) > 0
        finally:
            container.close()
    except Exception:
        return False


def _ffmpeg_escape_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
            .replace("'", "'\\''")
            .replace(":", "\\:")
            .replace("%", "%%")
    )


def _drawtext_y_expr(position: str, pad: int) -> str:
    if position == "top":
        return f"{pad}"
    if position == "bottom":
        return f"h-th-{pad}"
    return "(h-th)/2"


def _overlay_xy_expr(position: str, pad: int) -> str:
    if position == "bottom_left":
        return f"{pad}:main_h-overlay_h-{pad}"
    if position == "top_right":
        return f"main_w-overlay_w-{pad}:{pad}"
    if position == "top_left":
        return f"{pad}:{pad}"
    return f"main_w-overlay_w-{pad}:main_h-overlay_h-{pad}"


def render_video_ad(plan: dict, *, background: str, output: str) -> None:
    """Burn text + image overlays into a base video; loudnorm if audio is present."""
    import shutil
    import subprocess
    import tempfile

    kind = plan.get("kind")
    if kind != "video":
        raise ValueError(f"render_video_ad called on non-video plan: {kind!r}")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH")
    if not Path(background).exists():
        raise FileNotFoundError(f"Background video not found: {background}")

    overlays = plan.get("overlays") or []
    width = int(plan.get("width") or 1080)
    height = int(plan.get("height") or 1920)
    lufs_target = plan.get("lufs_target")

    image_overlays = [
        o for o in overlays
        if o.get("type") == "image"
        and o.get("path") and Path(o["path"]).exists()
    ]
    text_overlays = [
        o for o in overlays
        if o.get("type") == "text" and o.get("text")
    ]
    if text_overlays and not has_drawtext():
        raise RuntimeError(
            "ffmpeg lacks the drawtext filter. Install an ffmpeg build with "
            "freetype/fontconfig (e.g. `brew install ffmpeg --with-freetype` "
            "or use a static jellyfin/BtbN build)."
        )

    Path(output).parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="adclip_video_") as tmp:
        burned = str(Path(tmp) / "burned.mp4")
        cmd = ["ffmpeg", "-y", "-i", background]
        for img in image_overlays:
            cmd += ["-i", img["path"]]

        filters: list[str] = []
        last = "[0:v]"

        scale_label = "[scaled]"
        filters.append(
            f"{last}scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1{scale_label}"
        )
        last = scale_label

        for i, img in enumerate(image_overlays, start=1):
            max_w = int(img.get("max_width", 200))
            pad = int(img.get("pad", 32))
            xy = _overlay_xy_expr(img.get("position", "bottom_right"), pad)
            scaled = f"[wm{i}]"
            filters.append(f"[{i}:v]scale={max_w}:-1{scaled}")
            new = f"[v{i}]"
            filters.append(f"{last}{scaled}overlay={xy}{new}")
            last = new

        for j, txt in enumerate(text_overlays):
            font_size = int(txt.get("font_size", 48))
            pad = int(txt.get("pad", 48))
            color = txt.get("color", "#ffffff").lstrip("#")
            stroke = txt.get("stroke", "#000000").lstrip("#")
            y_expr = _drawtext_y_expr(txt.get("position", "top"), pad)
            x_expr = "(w-tw)/2"
            escaped = _ffmpeg_escape_text(txt["text"])
            new = f"[txt{j}]"
            filters.append(
                f"{last}drawtext=text='{escaped}':fontsize={font_size}"
                f":fontcolor=0x{color}:bordercolor=0x{stroke}:borderw=4"
                f":x={x_expr}:y={y_expr}{new}"
            )
            last = new

        has_audio = _has_audio(background)
        cmd += ["-filter_complex", ";".join(filters), "-map", last]
        if has_audio:
            cmd += ["-map", "0:a"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p"]
        if has_audio:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        cmd += [burned]

        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            err = proc.stderr.decode(errors="replace")[-500:]
            raise RuntimeError(f"ffmpeg overlay step failed: {err}")

        if lufs_target is not None and _has_audio(burned):
            from adclip._video_backend import loudnorm

            ok, _msg = loudnorm(
                burned, target=str(lufs_target), output_path=output,
            )
            if not ok:
                shutil.move(burned, output)
        else:
            shutil.move(burned, output)


def render_static_ad(plan: dict, *, background: str, output: str) -> None:
    kind = plan.get("kind")
    if kind != "static":
        raise ValueError(f"render_static_ad called on non-static plan: {kind!r}")

    overlays = plan.get("overlays") or []
    img = Image.open(background).convert("RGBA")

    for ov in overlays:
        if ov.get("type") == "image":
            _paste_image_overlay(img, ov)

    draw = ImageDraw.Draw(img)
    for ov in overlays:
        if ov.get("type") == "text":
            _draw_text_overlay(draw, ov, img.width, img.height)

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(output)
