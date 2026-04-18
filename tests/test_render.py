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
