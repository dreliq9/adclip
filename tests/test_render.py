import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from adclip.render import render_static_ad


def _make_blank_image(path: Path, w: int = 1080, h: int = 1350) -> None:
    img = Image.new("RGB", (w, h), color=(64, 64, 64))
    img.save(path)


@pytest.fixture
def tmp_bg(tmp_path):
    bg = tmp_path / "bg.png"
    _make_blank_image(bg)
    return bg


def test_render_draws_logo_image_overlay(tmp_bg, tmp_path):
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (200, 200), color=(255, 0, 255, 255)).save(logo)

    out = tmp_path / "out.png"
    plan = {
        "format": "meta_feed_4x5",
        "kind": "static",
        "overlays": [
            {
                "type": "image", "role": "logo",
                "path": str(logo),
                "position": "bottom_right",
                "pad": 32,
                "max_width": 100,
            },
        ],
        "copy": {"headline": "H", "body": "B", "cta": "CTA", "angle": "a"},
    }
    render_static_ad(plan, background=str(tmp_bg), output=str(out))

    rendered = Image.open(out).convert("RGB")
    w, h = rendered.size
    # logo is 100x100 after resize; anchored pad=32 from bottom-right edge.
    # Sample 10px inside that square.
    probe_x = w - 32 - 50
    probe_y = h - 32 - 50
    r, g, b = rendered.getpixel((probe_x, probe_y))
    assert (r, g, b) == (255, 0, 255), f"expected magenta logo pixel, got {(r, g, b)}"


def test_render_missing_plan_kind_raises_clean_valueerror(tmp_bg, tmp_path):
    out = tmp_path / "out.png"
    with pytest.raises(ValueError, match="non-static plan"):
        render_static_ad({"overlays": []}, background=str(tmp_bg), output=str(out))


def test_render_tolerates_overlay_without_text(tmp_bg, tmp_path):
    out = tmp_path / "out.png"
    plan = {
        "kind": "static",
        "overlays": [
            {"type": "text", "role": "headline"},  # no 'text' key
            {"type": "text", "role": "cta", "text": "Only real overlay"},
        ],
    }
    render_static_ad(plan, background=str(tmp_bg), output=str(out))
    assert out.exists()


def test_render_continues_when_logo_file_missing(tmp_bg, tmp_path):
    out = tmp_path / "out.png"
    plan = {
        "kind": "static",
        "overlays": [
            {
                "type": "image", "role": "logo",
                "path": str(tmp_path / "does_not_exist.png"),
                "position": "bottom_right", "pad": 32, "max_width": 100,
            },
            {
                "type": "text", "role": "headline",
                "text": "Still draws", "position": "top", "pad": 48,
                "font_size": 60, "color": "#ffffff", "stroke": "#000000",
            },
        ],
    }
    render_static_ad(plan, background=str(tmp_bg), output=str(out))
    assert out.exists()


def test_render_tolerates_missing_overlays_key(tmp_bg, tmp_path):
    out = tmp_path / "out.png"
    render_static_ad({"kind": "static"}, background=str(tmp_bg), output=str(out))
    assert out.exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_render_static_produces_file(tmp_bg, tmp_path):
    out = tmp_path / "out.png"
    plan = {
        "format": "meta_feed_4x5",
        "kind": "static",
        "overlays": [
            {
                "type": "text", "role": "headline",
                "text": "Start Paper Trading",
                "position": "top", "pad": 48,
                "font_size": 60, "color": "#ffffff", "stroke": "#000000",
            },
            {
                "type": "text", "role": "cta",
                "text": "Try Free",
                "position": "bottom", "pad": 48,
                "font_size": 48, "color": "#ffffff", "stroke": "#000000",
            },
        ],
        "copy": {"headline": "H", "body": "B", "cta": "CTA", "angle": "a"},
    }
    render_static_ad(plan, background=str(tmp_bg), output=str(out))
    assert out.exists()
    # File should be non-trivial size
    assert out.stat().st_size > 5_000
