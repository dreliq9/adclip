"""Small media-provider adapters shared by CLI, MCP, and application tests.

The production ``default`` path remains in ``adclip.pipeline`` for now. These
helpers remove test-provider code from the MCP adapter and establish a neutral
home for future image/video provider registries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable


MediaProviderFn = Callable[..., object]


def fake_image_provider(prompt, *, format_name, output_dir, seed):
    from PIL import Image

    from adclip.formats import get_format

    del prompt
    fmt = get_format(format_name)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = Path(output_dir) / f"{format_name}_{seed or 'x'}.png"
    Image.new("RGB", (fmt.width, fmt.height), color=(20, 20, 40)).save(path)

    class Result:
        local_path = str(path)
        url = ""
        model = "flux-fake"
        cost_usd = 0.0

    return Result()


def fake_video_provider(prompt, *, format_name, output_dir, seed):
    """Synthesize a one-second test MP4 via FFmpeg lavfi."""

    import subprocess

    from adclip.formats import get_format

    del prompt
    fmt = get_format(format_name)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = Path(output_dir) / f"{format_name}_{seed or 'x'}_raw.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration=1:size={fmt.width}x{fmt.height}:rate=30",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    class Result:
        local_path = str(path)
        url = ""
        model = "kling-fake"
        cost_usd = 0.0
        duration = 1.0

    return Result()


def resolve_image_provider(name: str) -> MediaProviderFn | None:
    if name == "default":
        return None
    if name == "fake":
        return fake_image_provider
    raise ValueError(f"Unknown image provider: {name!r}")


def resolve_video_provider(name: str) -> MediaProviderFn | None:
    if name == "default":
        return None
    if name == "fake":
        return fake_video_provider
    raise ValueError(f"Unknown video provider: {name!r}")
