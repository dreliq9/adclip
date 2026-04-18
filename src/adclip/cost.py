"""Pre-run cost estimator. Errs high so real cost <= estimate."""

from __future__ import annotations

from dataclasses import dataclass

from adclip.formats import get_format
from adclip.schema import AdBrief


# Rates (USD) — conservative / high-end estimates
FLUX_DEV_PER_IMAGE = 0.025
KLING_26_PER_SECOND = 0.07
DEFAULT_VIDEO_DURATION_S = 6.0

# LLM: claude sonnet pricing ~$3/M input + $15/M output, padded
LLM_TOKENS_PER_CANDIDATE = 600  # input + output rough
LLM_COST_PER_1K_TOKENS = 0.009  # blended


@dataclass(frozen=True)
class CostEstimate:
    llm_cost_usd: float
    image_cost_usd: float
    video_cost_usd: float
    total_usd: float
    over_budget: bool
    budget_usd: float | None
    breakdown: dict[str, float]


def estimate_cost(brief: AdBrief) -> CostEstimate:
    # LLM: pool_size candidates generated per (format × angle) combo
    llm_calls = brief.pool_size * len(brief.formats) * len(brief.angles)
    llm_cost = (llm_calls * LLM_TOKENS_PER_CANDIDATE / 1000.0) * LLM_COST_PER_1K_TOKENS

    image_cost = 0.0
    video_cost = 0.0
    per_format: dict[str, float] = {}

    for fmt_name in brief.formats:
        fmt = get_format(fmt_name)
        if fmt.kind == "static":
            c = brief.variants * FLUX_DEV_PER_IMAGE
            image_cost += c
            per_format[fmt_name] = c
        elif fmt.kind == "video":
            c = brief.variants * DEFAULT_VIDEO_DURATION_S * KLING_26_PER_SECOND
            video_cost += c
            per_format[fmt_name] = c
        else:  # text
            per_format[fmt_name] = 0.0

    total = llm_cost + image_cost + video_cost
    over = brief.budget_usd is not None and total > brief.budget_usd

    return CostEstimate(
        llm_cost_usd=round(llm_cost, 4),
        image_cost_usd=round(image_cost, 4),
        video_cost_usd=round(video_cost, 4),
        total_usd=round(total, 4),
        over_budget=over,
        budget_usd=brief.budget_usd,
        breakdown=per_format,
    )
