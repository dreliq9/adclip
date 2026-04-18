"""Copy generation orchestrator: prompt construction + pool generation."""

from __future__ import annotations

from adclip.formats import get_format
from adclip.llm import LLMProvider, parse_copy_candidates
from adclip.schema import AdBrief


_PROMPT_TEMPLATE = """\
You are an expert performance-ad copywriter. Write ad copy for this brief.

Product: {product}
Value proposition: {value_prop}
Audience: {audience}
Tone: {tone}
CTA direction: {cta}

Creative angle for this batch: {angle}
(Stay in this angle; we vary angles across batches.)

Target format: {format_name}
- Headline max: {headline_max} characters
- Body max: {body_max} characters

Must include (if provided): {must_include}
Must avoid (if provided): {must_avoid}

Generate {n} distinct candidate ads. Each candidate must respect the char
limits strictly. Return JSON only, no prose, in this exact shape:

{{
  "candidates": [
    {{"headline": "...", "body": "...", "cta": "..."}},
    ...
  ]
}}
"""


def build_prompt(brief: AdBrief, *, format_name: str, angle: str) -> str:
    fmt = get_format(format_name)
    return _PROMPT_TEMPLATE.format(
        product=brief.product,
        value_prop=brief.value_prop,
        audience=brief.audience,
        tone=brief.tone,
        cta=brief.cta,
        angle=angle,
        format_name=format_name,
        headline_max=fmt.headline_max,
        body_max=fmt.body_max,
        must_include=", ".join(brief.must_include) or "(none)",
        must_avoid=", ".join(brief.must_avoid) or "(none)",
        n=brief.pool_size,
    )


def generate_copy_pool(
    brief: AdBrief, *, provider: LLMProvider
) -> list[dict]:
    """Generate a candidate pool across (format x angle) combos.

    Each candidate dict has keys: headline, body, cta, format, angle.
    Candidates are NOT yet policy-filtered or ranked — that happens
    in policy.py and scoring.py.
    """
    pool: list[dict] = []
    for fmt_name in brief.formats:
        for angle in brief.angles:
            prompt = build_prompt(brief, format_name=fmt_name, angle=angle)
            raw = provider.generate(prompt, n=brief.pool_size)
            cands = parse_copy_candidates(raw)
            for c in cands:
                pool.append({
                    **c,
                    "format": fmt_name,
                    "angle": angle,
                })
    return pool
