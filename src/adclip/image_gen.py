"""Static image generation through fal.ai model adapters.

Image models do not share a universal request schema. This module keeps a
small, explicit model profile for each supported family and builds only the
arguments that family accepts. Raw fal endpoint IDs remain available as a
best-effort generic path.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.request import urlretrieve

from adclip.formats import get_format
from adclip.schema import AdBrief


@dataclass(frozen=True)
class FalImageModelSpec:
    endpoint: str
    request_style: str
    default_options: Mapping[str, object] = field(default_factory=dict)


MODEL_SPECS: dict[str, FalImageModelSpec] = {
    "gpt-image-2": FalImageModelSpec(
        "openai/gpt-image-2",
        "gpt-image",
        {"quality": "medium", "output_format": "png"},
    ),
    "nano-banana-2": FalImageModelSpec(
        "fal-ai/nano-banana-2",
        "nano-banana",
        {"resolution": "1K", "output_format": "png"},
    ),
    "nano-banana-pro": FalImageModelSpec(
        "fal-ai/nano-banana-pro",
        "nano-banana",
        {"resolution": "2K", "output_format": "png"},
    ),
    "nano-banana-2-lite": FalImageModelSpec(
        "google/nano-banana-2-lite",
        "nano-banana-lite",
        {"output_format": "png"},
    ),
    "flux-2": FalImageModelSpec("fal-ai/flux-2", "flux", {}),
    "flux-2-pro": FalImageModelSpec("fal-ai/flux-2-pro", "flux", {}),
    "flux-2-flex": FalImageModelSpec("fal-ai/flux-2-flex", "flux", {}),
    "flux-2-max": FalImageModelSpec("fal-ai/flux-2-max", "flux", {}),
    "flux-schnell": FalImageModelSpec("fal-ai/flux/schnell", "flux", {}),
    "flux-dev": FalImageModelSpec("fal-ai/flux/dev", "flux", {}),
    "flux-pro": FalImageModelSpec("fal-ai/flux-pro", "flux", {}),
    "imagen-3": FalImageModelSpec("fal-ai/imagen3", "generic", {}),
}

MODELS: dict[str, str] = {name: spec.endpoint for name, spec in MODEL_SPECS.items()}

COST_PER_IMAGE: dict[str, float] = {
    "gpt-image-2": 0.053,
    "nano-banana-2": 0.080,
    "nano-banana-pro": 0.150,
    "nano-banana-2-lite": 0.040,
    "flux-2": 0.020,
    "flux-2-pro": 0.030,
    "flux-2-flex": 0.050,
    "flux-2-max": 0.070,
    "flux-schnell": 0.003,
    "flux-dev": 0.025,
    "flux-pro": 0.050,
    "imagen-3": 0.040,
}


@dataclass(frozen=True)
class ImageResult:
    local_path: str
    url: str
    model: str
    cost_usd: float


def _check_key() -> None:
    from adclip._live_apis import require_live_apis

    require_live_apis("fal.ai image generation")
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError(
            "FAL_KEY not set. Get your key at https://fal.ai/dashboard/keys"
        )


def build_image_prompt(
    brief: AdBrief, *, format_name: str, variant_copy: dict
) -> str:
    fmt = get_format(format_name)
    colors = ", ".join(brief.brand_colors) if brief.brand_colors else "brand-agnostic"
    aspect_hint = f"{fmt.aspect} aspect ratio ({fmt.width}x{fmt.height} px)"
    return (
        f"Professional advertising image for {brief.product}. "
        f"{brief.value_prop} "
        f"Targeting: {brief.audience}. "
        f"Creative angle: {variant_copy.get('angle', '')}. "
        f"Tone: {brief.tone}. "
        f"Brand palette: {colors}. "
        f"Format: {aspect_hint}. "
        "Clean composition, leave negative space at top and bottom for "
        "headline and CTA overlays. Photorealistic, high detail, commercial-grade."
    )


def _round_to_multiple(value: int, multiple: int = 16) -> int:
    return max(multiple, round(value / multiple) * multiple)


def _custom_size(format_name: str) -> dict[str, int]:
    fmt = get_format(format_name)
    return {
        "width": _round_to_multiple(fmt.width),
        "height": _round_to_multiple(fmt.height),
    }


def _aspect_ratio(format_name: str) -> str:
    aspect = get_format(format_name).aspect
    if aspect in {"1:1", "4:5", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"}:
        return aspect
    if aspect == "1.91:1":
        return "16:9"
    return "auto"


def resolve_model_spec(model: str) -> FalImageModelSpec:
    if model in MODEL_SPECS:
        return MODEL_SPECS[model]
    if "/" not in model or model.startswith(("http://", "https://")):
        raise ValueError(
            f"Unknown image model alias: {model!r}. Use one of "
            f"{sorted(MODEL_SPECS)} or pass a raw fal endpoint ID."
        )
    lowered = model.lower()
    if "gpt-image" in lowered:
        style = "gpt-image"
    elif "nano-banana" in lowered and "lite" in lowered:
        style = "nano-banana-lite"
    elif "nano-banana" in lowered:
        style = "nano-banana"
    elif "flux" in lowered:
        style = "flux"
    else:
        style = "generic"
    return FalImageModelSpec(model, style, {})


def resolve_model_endpoint(model: str) -> str:
    return resolve_model_spec(model).endpoint


def build_generation_arguments(
    prompt: str,
    *,
    format_name: str,
    model: str,
    seed: int | None = None,
    options: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a schema-aware fal request without making a network call."""

    spec = resolve_model_spec(model)
    config = {**dict(spec.default_options), **dict(options or {})}
    output_format = str(config.get("output_format", "png"))

    if spec.request_style == "gpt-image":
        arguments: dict[str, object] = {
            "prompt": prompt,
            "image_size": _custom_size(format_name),
            "quality": str(config.get("quality", "medium")),
            "num_images": int(config.get("num_images", 1)),
            "output_format": output_format,
        }
        if "openai_api_key" in config:
            arguments["openai_api_key"] = config["openai_api_key"]
        return arguments

    if spec.request_style in {"nano-banana", "nano-banana-lite"}:
        arguments = {
            "prompt": prompt,
            "aspect_ratio": str(config.get("aspect_ratio", _aspect_ratio(format_name))),
            "num_images": int(config.get("num_images", 1)),
            "output_format": output_format,
        }
        if spec.request_style != "nano-banana-lite":
            arguments["resolution"] = str(config.get("resolution", "1K"))
        if seed is not None:
            arguments["seed"] = seed
        for key in (
            "enable_web_search",
            "enable_google_search",
            "thinking_level",
            "limit_generations",
        ):
            if key in config:
                arguments[key] = config[key]
        return arguments

    arguments = {
        "prompt": prompt,
        "image_size": _custom_size(format_name),
        "num_images": int(config.get("num_images", 1)),
    }
    if seed is not None:
        arguments["seed"] = seed
    if "output_format" in config:
        arguments["output_format"] = output_format
    for key in ("guidance_scale", "num_inference_steps", "safety_tolerance"):
        if key in config:
            arguments[key] = config[key]
    return arguments


def estimate_image_cost(
    model: str,
    n: int,
    *,
    format_name: str | None = None,
    options: Mapping[str, object] | None = None,
) -> float:
    config = dict(options or {})
    if model == "gpt-image-2":
        quality = str(config.get("quality", "medium"))
        base = {"low": 0.006, "medium": 0.053, "high": 0.211}.get(quality, 0.211)
        if format_name:
            fmt = get_format(format_name)
            base *= max(0.5, (fmt.width * fmt.height) / (1024 * 1024))
        return round(base * n, 4)
    if model == "nano-banana-2":
        multiplier = {"0.5K": 0.75, "1K": 1.0, "2K": 1.5, "4K": 2.0}.get(
            str(config.get("resolution", "1K")), 1.0
        )
        return round(0.08 * multiplier * n, 4)
    return round(COST_PER_IMAGE.get(model, 0.05) * n, 4)


def generate_image(
    prompt: str,
    *,
    format_name: str,
    model: str = "gpt-image-2",
    output_dir: str,
    seed: int | None = None,
    options: Mapping[str, object] | None = None,
) -> ImageResult:
    """Generate one image through a schema-aware fal adapter."""

    import fal_client

    _check_key()
    spec = resolve_model_spec(model)
    arguments = build_generation_arguments(
        prompt,
        format_name=format_name,
        model=model,
        seed=seed,
        options=options,
    )
    result = fal_client.subscribe(spec.endpoint, arguments=arguments, with_logs=False)
    images = result.get("images")
    if not isinstance(images, list) or not images:
        raise RuntimeError(f"fal image response for {model!r} did not contain images[]")
    url = images[0]["url"]

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_format = str(dict(options or {}).get("output_format", "png"))
    extension = "jpg" if output_format == "jpeg" else output_format
    fname = f"{format_name}_{seed or 'x'}.{extension}"
    local = str(Path(output_dir) / fname)
    urlretrieve(url, local)

    return ImageResult(
        local_path=local,
        url=url,
        model=model,
        cost_usd=estimate_image_cost(
            model,
            1,
            format_name=format_name,
            options=options,
        ),
    )
