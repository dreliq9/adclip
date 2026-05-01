"""AI video generation via fal.ai — Kling, Wan, Veo, Sora, and other models.

Requires FAL_KEY environment variable to be set.

Model catalog + per-second cost data live in adclip._video_backend, which
is a vendored slice of declip.fetch_models. Sync there when fal.ai adds
new model families or redesigns its explore page.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlretrieve

import fal_client

from adclip._video_backend import (
    ALIASES as MODELS,
    MODEL_COST_PER_SEC as _ENDPOINT_COSTS,
    cost_per_sec as _cost_per_sec,
    resolve_endpoint,
    to_image_to_video,
)

# Alias-keyed cost view kept for back-compat with any caller that imports
# this constant directly. Prefer cost_per_sec(model) for new code.
MODEL_COST_PER_SEC: dict[str, float] = {
    alias: _ENDPOINT_COSTS[endpoint]
    for alias, endpoint in MODELS.items()
    if endpoint in _ENDPOINT_COSTS
}


def _check_key():
    from adclip._live_apis import require_live_apis

    require_live_apis("fal.ai video generation")
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError(
            "FAL_KEY environment variable not set. "
            "Get your key at https://fal.ai/dashboard/keys"
        )


@dataclass
class GenerationResult:
    video_url: str
    local_path: str | None
    model: str
    duration: float
    estimated_cost: float
    seed: int | None = None


@dataclass(frozen=True)
class VideoResult:
    local_path: str
    url: str
    model: str
    cost_usd: float
    duration: float


def _progress_callback(update):
    """Print progress during generation."""
    if isinstance(update, fal_client.InProgress):
        for log in update.logs:
            print(f"    {log['message']}", file=sys.stderr)


def generate_video(
    prompt: str,
    model: str = "kling-3",
    duration: int = 5,
    aspect_ratio: str = "16:9",
    output_path: str | Path | None = None,
    image_path: str | Path | None = None,
    end_image_path: str | Path | None = None,
    negative_prompt: str | None = None,
    generate_audio: bool = False,
    seed: int | None = None,
    resolution: str | None = None,
    progress_callback=None,
) -> GenerationResult:
    """Generate a video clip using fal.ai.

    Args:
        prompt: Text description of the video to generate
        model: Alias from MODELS (e.g. "kling-3", "veo-3.1") or raw endpoint
        duration: Duration in seconds (model-dependent, typically 3-15)
        aspect_ratio: "16:9", "9:16", or "1:1"
        output_path: Where to save the video (None = don't download)
        image_path: Start image for image-to-video models
        end_image_path: End image (Kling only)
        negative_prompt: What to avoid
        generate_audio: Generate audio with video (Kling 3.0 only)
        seed: Reproducibility seed
        resolution: Resolution for Wan models ("480p", "720p", "1080p")
        progress_callback: Function called with fal_client queue updates
    """
    _check_key()

    endpoint = resolve_endpoint(model)
    if image_path:
        endpoint = to_image_to_video(endpoint)

    args: dict = {
        "prompt": prompt,
        "duration": str(duration),
        "aspect_ratio": aspect_ratio,
    }

    if negative_prompt:
        args["negative_prompt"] = negative_prompt
    if seed is not None:
        args["seed"] = seed

    if "kling" in endpoint:
        if generate_audio:
            args["generate_audio"] = True
        if image_path:
            args["start_image_url"] = _upload_image(image_path)
            if end_image_path:
                args["end_image_url"] = _upload_image(end_image_path)
    elif "wan" in endpoint:
        if resolution:
            args["resolution"] = resolution
        args["enable_prompt_expansion"] = True
        if image_path:
            args["image_url"] = _upload_image(image_path)

    cb = progress_callback or _progress_callback
    result = fal_client.subscribe(
        endpoint,
        arguments=args,
        with_logs=True,
        on_queue_update=cb,
    )

    video_url = result["video"]["url"]
    result_seed = result.get("seed")

    cost = _cost_per_sec(model) or _cost_per_sec(endpoint) or 0.10
    estimated_cost = cost * duration
    if generate_audio and "kling" in endpoint:
        estimated_cost *= 1.5

    local = None
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        urlretrieve(video_url, str(output_path))
        local = str(output_path)

    return GenerationResult(
        video_url=video_url,
        local_path=local,
        model=model,
        duration=duration,
        estimated_cost=round(estimated_cost, 3),
        seed=result_seed,
    )


def _upload_image(path: str | Path) -> str:
    """Upload a local image to fal.ai CDN."""
    path = Path(path)
    if str(path).startswith(("http://", "https://")):
        return str(path)
    return fal_client.upload_file(str(path))


def generate_batch(
    specs: list[dict],
    output_dir: str | Path = "generated",
) -> list[GenerationResult]:
    """Generate multiple videos from a list of specs.

    Each spec is a dict with keys matching generate_video() args:
    {"prompt": "...", "model": "kling-3", "duration": 5, ...}
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, spec in enumerate(specs):
        out_path = output_dir / f"gen_{i:03d}.mp4"
        spec.setdefault("output_path", str(out_path))

        print(f"  [{i+1}/{len(specs)}] Generating: {spec.get('prompt', '')[:60]}...",
              file=sys.stderr)

        try:
            result = generate_video(**spec)
            results.append(result)
        except Exception as e:
            print(f"    Error: {e}", file=sys.stderr)

    return results


def estimate_cost(
    model: str = "kling-3",
    duration: int = 5,
    count: int = 1,
    audio: bool = False,
) -> dict:
    """Estimate generation cost without running anything.

    Returns dict with per-clip and total cost.
    """
    cost = _cost_per_sec(model) or 0.10
    per_clip = cost * duration
    if audio and "kling" in model:
        per_clip *= 1.5
    return {
        "model": model,
        "duration_sec": duration,
        "clips": count,
        "cost_per_clip": round(per_clip, 3),
        "total_cost": round(per_clip * count, 2),
        "audio_included": audio,
    }


def generate_ad_clip(
    prompt: str,
    *,
    format_name: str,
    output_dir: str,
    seed: int | None = None,
    model: str = "kling-2.6",
    duration: int = 5,
) -> VideoResult:
    """Generate one fal.ai clip sized for the given video ad format.

    Mirrors ``image_gen.generate_image``: returns a raw clip path. Overlay
    burn-in and loudness normalization happen downstream in
    ``render.render_video_ad``.
    """
    from adclip.formats import get_format

    fmt = get_format(format_name)
    if fmt.kind != "video":
        raise ValueError(f"format {format_name!r} is not a video format")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    fname = f"{format_name}_{seed or 'x'}_raw.mp4"
    local = str(Path(output_dir) / fname)

    result = generate_video(
        prompt=prompt,
        model=model,
        duration=duration,
        aspect_ratio=fmt.aspect,
        output_path=local,
        seed=seed,
    )

    return VideoResult(
        local_path=result.local_path or local,
        url=result.video_url,
        model=result.model,
        cost_usd=result.estimated_cost,
        duration=float(result.duration),
    )


def list_models() -> dict[str, dict]:
    """List available aliased models with pricing info."""
    result = {}
    for name, endpoint in MODELS.items():
        is_i2v = "image-to-video" in endpoint
        cost = _cost_per_sec(name) or 0.10
        result[name] = {
            "endpoint": endpoint,
            "type": "image-to-video" if is_i2v else "text-to-video",
            "cost_per_sec": cost,
            "cost_5sec": round(cost * 5, 2),
        }
    return result
