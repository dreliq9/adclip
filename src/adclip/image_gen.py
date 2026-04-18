"""Static image generation via fal.ai.

Wraps Flux and Imagen models. Produces raw visual assets; overlays/text
are burned in by compose.py using the ffmpeg backend.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlretrieve

from adclip.formats import get_format
from adclip.schema import AdBrief


MODELS: dict[str, str] = {
    "flux-schnell": "fal-ai/flux/schnell",
    "flux-dev": "fal-ai/flux/dev",
    "flux-pro": "fal-ai/flux-pro",
    "imagen-3": "fal-ai/imagen3",
}

COST_PER_IMAGE: dict[str, float] = {
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
        f"Clean composition, leave negative space at top and bottom for headline and CTA overlays. "
        f"Photorealistic, high detail, commercial-grade."
    )


def estimate_image_cost(model: str, n: int) -> float:
    return COST_PER_IMAGE.get(model, 0.05) * n


def generate_image(
    prompt: str,
    *,
    format_name: str,
    model: str = "flux-dev",
    output_dir: str,
    seed: int | None = None,
) -> ImageResult:
    """Generate one image. Blocks until the fal job returns."""
    import fal_client  # imported lazily so tests don't need the key

    _check_key()
    fmt = get_format(format_name)
    model_id = MODELS.get(model)
    if not model_id:
        raise ValueError(f"Unknown image model: {model!r}. Options: {sorted(MODELS)}")

    args: dict = {
        "prompt": prompt,
        "image_size": {"width": fmt.width, "height": fmt.height},
        "num_images": 1,
    }
    if seed is not None:
        args["seed"] = seed

    result = fal_client.subscribe(model_id, arguments=args, with_logs=False)
    url = result["images"][0]["url"]

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    fname = f"{format_name}_{seed or 'x'}.png"
    local = str(Path(output_dir) / fname)
    urlretrieve(url, local)

    return ImageResult(
        local_path=local,
        url=url,
        model=model,
        cost_usd=estimate_image_cost(model, 1),
    )
