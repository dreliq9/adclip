"""Task-routed image and video provider bindings.

Routes choose a task-appropriate provider/model/options policy. Explicit
provider or model arguments still override that policy. Fallbacks are exposed
for planning and evaluation, but are not silently executed because a fallback
may create another paid request.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

from adclip.model_routing import (
    MediaRoute,
    ensure_route_executable,
    default_route_name,
    get_media_route,
    list_media_routes,
)
from adclip.runtime import ProviderRequirements, RuntimePolicy


MediaProviderFn = Callable[..., object]


@dataclass(frozen=True)
class MediaProviderBinding:
    """Callable media adapter plus selected route/provider/model identity."""

    media_kind: str
    provider_name: str
    model_name: str | None
    invoke: MediaProviderFn
    route_name: str | None = None
    options: Mapping[str, object] = field(default_factory=dict)

    def __call__(self, prompt, *, format_name, output_dir, seed):
        return self.invoke(
            prompt,
            format_name=format_name,
            output_dir=output_dir,
            seed=seed,
        )

    def as_dict(self) -> dict[str, str | None]:
        """Backward-compatible provider/model identity."""

        return {"provider": self.provider_name, "model": self.model_name}

    def provenance(self) -> dict[str, object]:
        result: dict[str, object] = self.as_dict()
        if self.route_name:
            result["route"] = self.route_name
        if self.options:
            result["options"] = dict(self.options)
        return result


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


def _route_selection(
    modality: str,
    *,
    route_name: str | None,
    provider_name: str,
    model_name: str | None,
    explicit_options: Mapping[str, object] | None,
) -> tuple[MediaRoute, str, str, dict[str, object]]:
    route = get_media_route(modality, route_name)  # type: ignore[arg-type]
    ensure_route_executable(route)
    provider_env = "ADCLIP_IMAGE_PROVIDER" if modality == "image" else "ADCLIP_VIDEO_PROVIDER"
    model_env = "ADCLIP_IMAGE_MODEL" if modality == "image" else "ADCLIP_VIDEO_MODEL"
    provider = (
        os.environ.get(provider_env, route.primary.provider)
        if provider_name == "default"
        else provider_name
    )
    target = route.target_for_provider(provider)
    if target is None and provider == route.primary.provider:
        target = route.primary
    if provider == "fake":
        default_model = "fake-image-v1" if modality == "image" else "fake-video-v1"
        selected_model = model_name or os.environ.get(model_env) or default_model
        options: dict[str, object] = {}
    else:
        selected_model = (
            model_name
            or os.environ.get(model_env)
            or (target.model if target is not None else route.primary.model)
        )
        if target is not None and selected_model == target.model:
            options = dict(target.options)
        elif selected_model == route.primary.model:
            options = dict(route.primary.options)
        else:
            # A model override from a different family must not inherit options
            # that were validated only for the route's original target.
            options = {}
    options.update(dict(explicit_options or {}))
    return route, provider, selected_model, options


def resolve_image_provider(
    name: str = "default",
    *,
    model: str | None = None,
    route: str | None = None,
    options: Mapping[str, object] | None = None,
    policy: RuntimePolicy | None = None,
) -> MediaProviderBinding:
    active_policy = policy or RuntimePolicy.from_env()
    selected_route, provider, selected_model, selected_options = _route_selection(
        "image",
        route_name=route,
        provider_name=name,
        model_name=model,
        explicit_options=options,
    )

    if provider == "fake":
        def _invoke(prompt, *, format_name, output_dir, seed):
            return fake_image_provider(
                prompt,
                format_name=format_name,
                output_dir=output_dir,
                seed=seed,
                model=selected_model,
            )
    elif provider == "fal":
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
                options=selected_options,
            )
    elif provider == "openai":
        def _invoke(prompt, *, format_name, output_dir, seed):
            active_policy.check_provider(
                "openai-image",
                ProviderRequirements(network=True, paid_api=True),
            )
            from adclip.providers.openai_image import generate_image

            return generate_image(
                prompt,
                format_name=format_name,
                output_dir=output_dir,
                seed=seed,
                model=selected_model,
                options=selected_options,
            )
    else:
        raise ValueError(
            f"Unknown image provider: {provider!r}. Known providers: fal, openai, fake"
        )

    return MediaProviderBinding(
        media_kind="image",
        provider_name=provider,
        model_name=selected_model,
        invoke=_invoke,
        route_name=selected_route.name,
        options=selected_options,
    )


def resolve_video_provider(
    name: str = "default",
    *,
    model: str | None = None,
    route: str | None = None,
    options: Mapping[str, object] | None = None,
    policy: RuntimePolicy | None = None,
) -> MediaProviderBinding:
    active_policy = policy or RuntimePolicy.from_env()
    selected_route, provider, selected_model, selected_options = _route_selection(
        "video",
        route_name=route,
        provider_name=name,
        model_name=model,
        explicit_options=options,
    )

    if provider == "fake":
        def _invoke(prompt, *, format_name, output_dir, seed):
            return fake_video_provider(
                prompt,
                format_name=format_name,
                output_dir=output_dir,
                seed=seed,
                model=selected_model,
            )
    elif provider == "fal":
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
                options=selected_options,
            )
    else:
        raise ValueError(
            f"Unknown video provider: {provider!r}. Known providers: fal, fake"
        )

    return MediaProviderBinding(
        media_kind="video",
        provider_name=provider,
        model_name=selected_model,
        invoke=_invoke,
        route_name=selected_route.name,
        options=selected_options,
    )


def _describe_configured_default(modality: str) -> dict[str, object]:
    try:
        binding = (
            resolve_image_provider("default", policy=RuntimePolicy())
            if modality == "image"
            else resolve_video_provider("default", policy=RuntimePolicy())
        )
        return binding.provenance()
    except (RuntimeError, ValueError) as exc:
        return {
            "route": default_route_name(modality),  # type: ignore[arg-type]
            "configuration_error": str(exc),
        }


def describe_media_configuration() -> dict[str, object]:
    """Return defaults and route catalog without making status brittle."""

    return {
        "image": {
            "configured_default": _describe_configured_default("image"),
            "providers": ["fal", "openai", "fake"],
            "model_override": True,
            "route_override": True,
            "routes": list_media_routes("image"),
            "automatic_fallback": False,
        },
        "video": {
            "configured_default": _describe_configured_default("video"),
            "providers": ["fal", "fake"],
            "model_override": True,
            "route_override": True,
            "routes": list_media_routes("video"),
            "automatic_fallback": False,
        },
    }
