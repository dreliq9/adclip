"""Pre-run cost estimator aligned with the active media routes."""

from __future__ import annotations

from dataclasses import dataclass

from adclip.formats import get_format
from adclip.image_gen import estimate_image_cost
from adclip.model_routing import get_media_route
from adclip.schema import AdBrief
from adclip.video_gen import estimate_video_cost


LLM_TOKENS_PER_CANDIDATE = 600
LLM_COST_PER_1K_TOKENS = 0.009


@dataclass(frozen=True)
class CostEstimate:
    llm_cost_usd: float
    image_cost_usd: float
    video_cost_usd: float
    total_usd: float
    over_budget: bool
    budget_usd: float | None
    breakdown: dict[str, float]


def estimate_cost(
    brief: AdBrief,
    *,
    image_route: str | None = None,
    image_model: str | None = None,
    video_route: str | None = None,
    video_model: str | None = None,
) -> CostEstimate:
    """Estimate the selected route primaries; ordered fallbacks are not billed."""

    llm_calls = brief.pool_size * len(brief.formats) * len(brief.angles)
    llm_cost = (
        llm_calls * LLM_TOKENS_PER_CANDIDATE / 1000.0
    ) * LLM_COST_PER_1K_TOKENS

    kinds = {get_format(name).kind for name in brief.formats}
    image_policy = get_media_route("image", image_route) if "static" in kinds else None
    video_policy = get_media_route("video", video_route) if "video" in kinds else None
    selected_image_model = (
        image_model or image_policy.primary.model if image_policy is not None else None
    )
    selected_video_model = (
        video_model or video_policy.primary.model if video_policy is not None else None
    )
    image_options = image_policy.primary.options if image_policy is not None else {}
    video_options = video_policy.primary.options if video_policy is not None else {}

    image_cost = 0.0
    video_cost = 0.0
    per_format: dict[str, float] = {}

    for format_name in brief.formats:
        format_spec = get_format(format_name)
        if format_spec.kind == "static":
            assert selected_image_model is not None
            cost = estimate_image_cost(
                selected_image_model,
                brief.variants,
                format_name=format_name,
                options=image_options,
            )
            image_cost += cost
            per_format[format_name] = cost
        elif format_spec.kind == "video":
            assert selected_video_model is not None
            duration = float(video_options.get("duration", 5))
            cost = estimate_video_cost(
                selected_video_model,
                duration,
                generate_audio=bool(video_options.get("generate_audio", False)),
                resolution=(
                    str(video_options["resolution"])
                    if "resolution" in video_options
                    else None
                ),
            ) * brief.variants
            video_cost += cost
            per_format[format_name] = cost
        else:
            per_format[format_name] = 0.0

    total = llm_cost + image_cost + video_cost
    over_budget = brief.budget_usd is not None and total > brief.budget_usd
    return CostEstimate(
        llm_cost_usd=round(llm_cost, 4),
        image_cost_usd=round(image_cost, 4),
        video_cost_usd=round(video_cost, 4),
        total_usd=round(total, 4),
        over_budget=over_budget,
        budget_usd=brief.budget_usd,
        breakdown=per_format,
    )
