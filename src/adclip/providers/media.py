"""Model-bound image and video provider adapters.

Provider selection and model selection are separate. The current production
adapter is fal.ai, but application and interface code only receive a callable
binding carrying neutral provider/model metadata.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from adclip.runtime import ProviderRequirements, RuntimePolicy


MediaProviderFn = Callable[..., object]


@dataclass(frozen=True)
class MediaProviderBinding:
    """Callable media adapter plus the selected provider/model identity."""

    media_kind: str
    provider_name: str
    model_name: str | None
    invoke: MediaProviderFn

    def __call__(self, prompt, *, format_name, output_dir, seed):
        return self.invoke(
            prompt,
            format_name=format_name,
            output_dir=output_dir,
            seed=seed,
        )

    def as_dict(self) -> dict[str, str | None]:
        return {
            "provider": self.provider_name,
            "model": self.model_name,
        }


def fake_image_provider(
    prompt, *, format_name, output_dir, seed, model="fake-image-v1"
):
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
        cost_usd = 0.0

    result = Result()
    result.model = model
    return result


def fake_video_provider(
    prompt, *, format_name, output_dir, seed, model="fake-video-v1"
):
    """Synthesize a one-second test MP4 via FFmpeg lavfi."""

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
        cost_usd = 0.0
        duration = 1.0

    result = Result()
    result.model = model
    return result


def _configured_provider(requested: str, env_name: str, fallback: str) -> str:
    if requested == "default":
        return os.environ.get(env_name, fallback)
    return requested


def resolve_image_provider(
    name: str = "default",
    *,
    model: str | None = None,
    policy: RuntimePolicy | None = None,
) -> MediaProviderBinding:
    active_policy = policy or RuntimePolicy.from_env()
    canonical = _configured_provider(name, "ADCLIP_IMAGE_PROVIDER", "fal")
    if canonical == "fake":
        selected_model = model or "fake-image-v1"

        def _invoke(prompt, *, format_name, output_dir, seed):
            return fake_image_provider(
                prompt,
                format_name=format_name,
                output_dir=output_dir,
                seed=seed,
                model=selected_model,
            )

        return MediaProviderBinding(
            media_kind="image",
            provider_name="fake",
            model_name=selected_model,
            invoke=_invoke,
        )
    if canonical == "fal":
        selected_model = model or os.environ.get("ADCLIP_IMAGE_MODEL") or "flux-dev"

        def _invoke(prompt, *, format_name, output_dir, seed):
            active_policy.check_provider(
                "fal-image",
                ProviderRequirements(network=True, paid_api=True),
            )
            from adclip.image_gen import generate_image

            return generate_image(
                prompt,
                format_name=format_name,
                output_dir=output_dir,
                seed=seed,
                model=selected_model,
            )

        return MediaProviderBinding(
            media_kind="image",
            provider_name="fal",
            model_name=selected_model,
            invoke=_invoke,
        )
    raise ValueError(
        f"Unknown image provider: {name!r}. Known providers: default, fal, fake"
    )


def resolve_video_provider(
    name: str = "default",
    *,
    model: str | None = None,
    policy: RuntimePolicy | None = None,
) -> MediaProviderBinding:
    active_policy = policy or RuntimePolicy.from_env()
    canonical = _configured_provider(name, "ADCLIP_VIDEO_PROVIDER", "fal")
    if canonical == "fake":
        selected_model = model or "fake-video-v1"

        def _invoke(prompt, *, format_name, output_dir, seed):
            return fake_video_provider(
                prompt,
                format_name=format_name,
                output_dir=output_dir,
                seed=seed,
                model=selected_model,
            )

        return MediaProviderBinding(
            media_kind="video",
            provider_name="fake",
            model_name=selected_model,
            invoke=_invoke,
        )
    if canonical == "fal":
        selected_model = model or os.environ.get("ADCLIP_VIDEO_MODEL") or "kling-2.6"

        def _invoke(prompt, *, format_name, output_dir, seed):
            active_policy.check_provider(
                "fal-video",
                ProviderRequirements(network=True, paid_api=True),
            )
            from adclip.video_gen import generate_ad_clip

            return generate_ad_clip(
                prompt,
                format_name=format_name,
                output_dir=output_dir,
                seed=seed,
                model=selected_model,
            )

        return MediaProviderBinding(
            media_kind="video",
            provider_name="fal",
            model_name=selected_model,
            invoke=_invoke,
        )
    raise ValueError(
        f"Unknown video provider: {name!r}. Known providers: default, fal, fake"
    )


def describe_media_configuration() -> dict[str, object]:
    """Return provider/model defaults without invoking any provider."""

    image = resolve_image_provider("default", policy=RuntimePolicy())
    video = resolve_video_provider("default", policy=RuntimePolicy())
    return {
        "image": {
            "configured_default": image.as_dict(),
            "providers": ["fal", "fake"],
            "model_override": True,
        },
        "video": {
            "configured_default": video.as_dict(),
            "providers": ["fal", "fake"],
            "model_override": True,
        },
    }
