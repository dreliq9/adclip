"""LLM-as-judge scoring.

Scores each candidate against the brief (angle adherence, tone, CTA
strength, specificity). Uses the same LLMProvider async protocol as
copy generation so it picks up MCP sampling by default.
"""

from __future__ import annotations

import json
import re

from adclip.llm import LLMProvider
from adclip.schema import AdBrief


_JUDGE_PROMPT = """\
You are a senior performance-ad reviewer. Score ONE ad candidate against a brief.

# Brief
Product: {product}
Value proposition: {value_prop}
Audience: {audience}
Tone: {tone}
CTA direction: {cta}
Creative angle for this batch: {angle}

# Candidate
Headline: {headline}
Body: {body}
CTA: {ad_cta}
Target format: {format_name}

# Scoring rubric (return ONE score in [0.0, 1.0])
- 0.9-1.0: on-brief angle, tight hook, audience-appropriate tone, specific, strong CTA
- 0.6-0.8: solid, minor weakness (slightly weak hook, vague CTA, generic tone)
- 0.3-0.5: partial miss (drifts off angle, wrong tone, or weak body)
- 0.0-0.2: off-brief, wrong audience, weak on every axis

# Flags (include when applicable; not all are required)
- weak_hook, wrong_tone, off_angle, vague_cta, generic_copy, overclaim, too_hype

# Response
Return JSON only, no prose. Exact shape:
{{
  "score": 0.0,
  "rationale": "one sentence.",
  "flags": ["..."]
}}
"""


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def build_judge_prompt(brief: AdBrief, candidate: dict) -> str:
    return _JUDGE_PROMPT.format(
        product=brief.product,
        value_prop=brief.value_prop,
        audience=brief.audience,
        tone=brief.tone,
        cta=brief.cta,
        angle=candidate.get("angle", ""),
        headline=candidate.get("headline", ""),
        body=candidate.get("body", ""),
        ad_cta=candidate.get("cta", ""),
        format_name=candidate.get("format", ""),
    )


def parse_judge_response(raw: str) -> dict:
    match = _JSON_OBJECT_RE.search(raw)
    if not match:
        raise ValueError(f"No JSON object in judge response: {raw[:200]}")
    obj = json.loads(match.group(0))
    score = float(obj.get("score", 0.0))
    score = max(0.0, min(1.0, score))
    return {
        "score": score,
        "rationale": str(obj.get("rationale", "")),
        "flags": list(obj.get("flags", [])),
    }


async def score_with_judge(
    candidate: dict, brief: AdBrief, *, provider: LLMProvider
) -> dict:
    """Return candidate augmented with judge_score, judge_rationale, judge_flags."""
    prompt = build_judge_prompt(brief, candidate)
    raw = await provider.generate(prompt, n=1)
    parsed = parse_judge_response(raw)
    return {
        **candidate,
        "judge_score": parsed["score"],
        "judge_rationale": parsed["rationale"],
        "judge_flags": parsed["flags"],
    }
