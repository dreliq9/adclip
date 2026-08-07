"""Schema-aware AI video generation through fal.ai.

The current route catalog prefers Kling O3 for general ads, Veo 3.1 for
premium cinematic work, and Seedance 2 for directed multi-shot work. Legacy
aliases and the vendored live catalog remain available for compatibility.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.request import urlretrieve

from adclip._video_backend import (
    ALIASES as _LEGACY_ALIASES,
    MODEL_COST_PER_SEC as _ENDPOINT_COSTS,
    cost_per_sec as _legacy_cost_per_sec,
    resolve_endpoint as _legacy_resolve_endpoint,
    to_image_to_video,
)


CURRENT_MODELS: dict[str, str] = {
    "kling-o3-standard": "fal-ai/kling-video/o3/standard/text-to-video",
    "kling-o3-standard-i2v": "fal-ai/kling-video/o3/standard/image-to-video",
    "kling-3-standard": "fal-ai/kling-video/v3/standard/text-to-video",
    "veo-3.1": "fal-ai/veo3.1",
    "veo-3.1-fast": "fal-ai/veo3.1/fast",
    "seedance-2": "bytedance/seedance-2.0/text-to-video",
    "seedance-2-fast": "bytedance/seedance-2.0/fast/text-to-video",
    "seedance-2-reference": "bytedance/seedance-2.0/reference-to-video",
    "wan-2.7": "fal-ai/wan/v2.7/text-to-video",
    "wan-2.6": "wan/v2.6/text-to-video",
}

MODELS: dict[str, str] = {**_LEGACY_ALIASES, **CURRENT_MODELS}

MODEL_COST_PER_SEC: dict[str, float] = {
    **{
        alias: _ENDPOINT_COSTS[endpoint]
        for alias, endpoint in _LEGACY_ALIASES.items()
        if endpoint in _ENDPOINT_COSTS
    },
    "kling-o3-standard": 0.084,
    "kling-3-standard": 0.084,
    "veo-3.1": 0.20,
    "veo-3.1-fast": 0.10,
    "seedance-2": 0.3034,
    "seedance-2-fast": 0.242,
    "wan-2.7": 0.10,
    "wan-2.6": 0.10,
}


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


def _check_key() -> None:
    from adclip._live_apis import require_live_apis

    require_live_apis("fal.ai video generation")
    if not os.environ.get("FAL_KEY"):
        raise RuntimeError(
            "FAL_KEY environment variable not set. "
            "Get your key at https://fal.ai/dashboard/keys"
        )


def resolve_video_endpoint(model: str) -> str:
    if model in CURRENT_MODELS:
        return CURRENT_MODELS[model]
    if model in _LEGACY_ALIASES:
        return _LEGACY_ALIASES[model]
    if "/" in model and not model.startswith(("http://", "https://")):
        return model
    return _legacy_resolve_endpoint(model)


def _nearest(value: int, allowed: tuple[int, ...]) -> int:
    return min(allowed, key=lambda candidate: (abs(candidate - value), -candidate))


def _duration_seconds(value: int | str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, str):
        if value == "auto":
            return minimum
        value = int(value.rstrip("s"))
    return max(minimum, min(maximum, int(value)))


def build_video_arguments(
    prompt: str,
    *,
    model: str,
    duration: int | str = 5,
    aspect_ratio: str = "16:9",
    image_path: str | Path | None = None,
    end_image_path: str | Path | None = None,
    negative_prompt: str | None = None,
    generate_audio: bool = False,
    seed: int | None = None,
    resolution: str | None = None,
    options: Mapping[str, object] | None = None,
) -> tuple[str, dict[str, object], float]:
    """Return endpoint, family-specific input, and effective duration."""

    config = dict(options or {})
    duration = config.get("duration", duration)  # type: ignore[assignment]
    aspect_ratio = str(config.get("aspect_ratio", aspect_ratio))
    generate_audio = bool(config.get("generate_audio", generate_audio))
    resolution = str(config.get("resolution", resolution or "")) or None
    endpoint = resolve_video_endpoint(model)
    if image_path and "image-to-video" not in endpoint:
        endpoint = to_image_to_video(endpoint)

    lowered = endpoint.lower()
    if "veo3.1" in lowered:
        seconds = _nearest(
            _duration_seconds(duration, minimum=4, maximum=8),
            (4, 6, 8),
        )
        args: dict[str, object] = {
            "prompt": prompt,
            "duration": f"{seconds}s",
            "aspect_ratio": aspect_ratio if aspect_ratio in {"16:9", "9:16"} else "16:9",
            "resolution": resolution or "1080p",
            "generate_audio": generate_audio,
        }
        if seed is not None:
            args["seed"] = seed
        if image_path:
            args["image_url"] = _upload_image(image_path)
        return endpoint, args, float(seconds)

    if "seedance-2.0" in lowered:
        if duration == "auto":
            duration_value = "auto"
            seconds = 8.0
        else:
            seconds_int = _duration_seconds(duration, minimum=4, maximum=15)
            duration_value = str(seconds_int)
            seconds = float(seconds_int)
        args = {
            "prompt": prompt,
            "duration": duration_value,
            "resolution": resolution or "720p",
            "aspect_ratio": aspect_ratio
            if aspect_ratio in {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}
            else "auto",
            "generate_audio": generate_audio,
        }
        if seed is not None:
            args["seed"] = seed
        if "bitrate_mode" in config:
            args["bitrate_mode"] = config["bitrate_mode"]
        end_user_id = config.get("end_user_id") or os.environ.get("ADCLIP_END_USER_ID")
        if end_user_id:
            args["end_user_id"] = end_user_id
        if image_path:
            args["image_url"] = _upload_image(image_path)
        if end_image_path:
            args["end_image_url"] = _upload_image(end_image_path)
        return endpoint, args, seconds

    if "kling-video" in lowered or "kling" in lowered:
        seconds = _duration_seconds(duration, minimum=3, maximum=15)
        args = {
            "prompt": prompt,
            "duration": str(seconds),
            "aspect_ratio": aspect_ratio
            if aspect_ratio in {"16:9", "9:16", "1:1"}
            else "16:9",
            "generate_audio": generate_audio,
        }
        if "shot_type" in config:
            args["shot_type"] = config["shot_type"]
        if "multi_prompt" in config:
            args["multi_prompt"] = config["multi_prompt"]
        if negative_prompt:
            args["negative_prompt"] = negative_prompt
        if image_path:
            args["start_image_url"] = _upload_image(image_path)
        if end_image_path:
            args["end_image_url"] = _upload_image(end_image_path)
        return endpoint, args, float(seconds)

    if "wan/v2.7" in lowered:
        seconds = _duration_seconds(duration, minimum=2, maximum=15)
        args = {
            "prompt": prompt,
            "duration": str(seconds),
            "resolution": resolution or "720p",
            "aspect_ratio": aspect_ratio
            if aspect_ratio in {"16:9", "9:16", "1:1", "4:3", "3:4"}
            else "16:9",
        }
        if seed is not None:
            args["seed"] = seed
        if negative_prompt:
            args["negative_prompt"] = negative_prompt
        if "audio_url" in config:
            args["audio_url"] = config["audio_url"]
        if "enable_prompt_expansion" in config:
            args["enable_prompt_expansion"] = config["enable_prompt_expansion"]
        return endpoint, args, float(seconds)

    if "wan/v2.6" in lowered:
        seconds = _nearest(
            _duration_seconds(duration, minimum=5, maximum=10),
            (5, 10),
        )
        args = {
            "prompt": prompt,
            "duration": str(seconds),
            "resolution": resolution or "720p",
            "aspect_ratio": aspect_ratio,
        }
        if seed is not None:
            args["seed"] = seed
        if negative_prompt:
            args["negative_prompt"] = negative_prompt
        return endpoint, args, float(seconds)

    seconds = _duration_seconds(duration, minimum=3, maximum=15)
    args = {
        "prompt": prompt,
        "duration": str(seconds),
        "aspect_ratio": aspect_ratio,
    }
    if seed is not None:
        args["seed"] = seed
    if negative_prompt:
        args["negative_prompt"] = negative_prompt
    return endpoint, args, float(seconds)


def _progress_callback(update) -> None:
    import fal_client

    if isinstance(update, fal_client.InProgress):
        for log in update.logs:
            print(f"    {log['message']}", file=sys.stderr)


def estimate_video_cost(
    model: str,
    duration: float,
    *,
    generate_audio: bool = False,
    resolution: str | None = None,
) -> float:
    base = MODEL_COST_PER_SEC.get(model)
    if base is None:
        endpoint = resolve_video_endpoint(model)
        base = _legacy_cost_per_sec(model) or _legacy_cost_per_sec(endpoint) or 0.10
    if model == "kling-o3-standard" and generate_audio:
        base = 0.112
    elif model == "kling-3-standard" and generate_audio:
        base = 0.126
    elif model == "veo-3.1" and generate_audio:
        base = 0.40
    elif model == "veo-3.1-fast" and generate_audio:
        base = 0.15
    elif model == "seedance-2" and resolution == "1080p":
        base = 0.682
    elif model in {"wan-2.7", "wan-2.6"} and resolution == "1080p":
        base = 0.15
    return round(float(base) * duration, 3)


def generate_video(
    prompt: str,
    model: str = "kling-o3-standard",
    duration: int | str = 5,
    aspect_ratio: str = "16:9",
    output_path: str | Path | None = None,
    image_path: str | Path | None = None,
    end_image_path: str | Path | None = None,
    negative_prompt: str | None = None,
    generate_audio: bool = False,
    seed: int | None = None,
    resolution: str | None = None,
    progress_callback=None,
    options: Mapping[str, object] | None = None,
) -> GenerationResult:
    """Generate a video using a model-family-specific request profile."""

    import fal_client

    _check_key()
    endpoint, args, effective_duration = build_video_arguments(
        prompt,
        model=model,
        duration=duration,
        aspect_ratio=aspect_ratio,
        image_path=image_path,
        end_image_path=end_image_path,
        negative_prompt=negative_prompt,
        generate_audio=generate_audio,
        seed=seed,
        resolution=resolution,
        options=options,
    )
    cb = progress_callback or _progress_callback
    result = fal_client.subscribe(
        endpoint,
        arguments=args,
        with_logs=True,
        on_queue_update=cb,
    )
    video = result.get("video")
    if not isinstance(video, dict) or not video.get("url"):
        raise RuntimeError(f"fal video response for {model!r} did not contain video.url")
    video_url = video["url"]
    result_seed = result.get("seed")

    local = None
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        urlretrieve(video_url, str(output_path))
        local = str(output_path)

    config = dict(options or {})
    effective_audio = bool(config.get("generate_audio", generate_audio))
    effective_resolution = str(config.get("resolution", resolution or "")) or None
    return GenerationResult(
        video_url=video_url,
        local_path=local,
        model=model,
        duration=effective_duration,
        estimated_cost=estimate_video_cost(
            model,
            effective_duration,
            generate_audio=effective_audio,
            resolution=effective_resolution,
        ),
        seed=result_seed,
    )


def _upload_image(path: str | Path) -> str:
    import fal_client

    text = str(path)
    if text.startswith(("http://", "https://")):
        return text
    return fal_client.upload_file(text)


def generate_batch(
    specs: list[dict],
    output_dir: str | Path = "generated",
) -> list[GenerationResult]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for i, spec in enumerate(specs):
        out_path = output_dir / f"gen_{i:03d}.mp4"
        spec.setdefault("output_path", str(out_path))
        print(
            f"  [{i+1}/{len(specs)}] Generating: {spec.get('prompt', '')[:60]}...",
            file=sys.stderr,
        )
        try:
            results.append(generate_video(**spec))
        except Exception as exc:
            print(f"    Error: {exc}", file=sys.stderr)
    return results


def estimate_cost(
    model: str = "kling-o3-standard",
    duration: int = 5,
    count: int = 1,
    audio: bool = False,
) -> dict:
    per_clip = estimate_video_cost(model, float(duration), generate_audio=audio)
    return {
        "model": model,
        "duration_sec": duration,
        "clips": count,
        "cost_per_clip": per_clip,
        "total_cost": round(per_clip * count, 2),
        "audio_included": audio,
    }


def generate_ad_clip(
    prompt: str,
    *,
    format_name: str,
    output_dir: str,
    seed: int | None = None,
    model: str = "kling-o3-standard",
    duration: int = 5,
    options: Mapping[str, object] | None = None,
) -> VideoResult:
    """Generate one raw fal clip sized for the requested ad format."""

    from adclip.formats import get_format

    fmt = get_format(format_name)
    if fmt.kind != "video":
        raise ValueError(f"format {format_name!r} is not a video format")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    fname = f"{format_name}_{seed or 'x'}_raw.mp4"
    local = str(Path(output_dir) / fname)
    config = dict(options or {})
    result = generate_video(
        prompt=prompt,
        model=model,
        duration=config.get("duration", duration),  # type: ignore[arg-type]
        aspect_ratio=fmt.aspect,
        output_path=local,
        seed=seed,
        generate_audio=bool(config.get("generate_audio", False)),
        resolution=str(config.get("resolution", "")) or None,
        options=config,
    )
    return VideoResult(
        local_path=result.local_path or local,
        url=result.video_url,
        model=result.model,
        cost_usd=result.estimated_cost,
        duration=float(result.duration),
    )


def list_models() -> dict[str, dict]:
    result = {}
    for name, endpoint in MODELS.items():
        is_i2v = "image-to-video" in endpoint
        cost = MODEL_COST_PER_SEC.get(name) or _legacy_cost_per_sec(name) or 0.10
        result[name] = {
            "endpoint": endpoint,
            "type": "image-to-video" if is_i2v else "text-to-video",
            "cost_per_sec": cost,
            "cost_5sec": round(cost * 5, 2),
        }
    return result
