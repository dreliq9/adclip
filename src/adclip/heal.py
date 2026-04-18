"""Policy self-heal.

When a candidate violates policy, ask the LLM to rewrite it addressing
the specific violation without changing the core value prop. Bounded
retries — if healing fails N times, give up (caller drops the candidate).
"""

from __future__ import annotations

from adclip.formats import get_format
from adclip.llm import LLMProvider, parse_copy_candidates
from adclip.policy import check_copy
from adclip.schema import AdBrief


_HEAL_PROMPT = """\
You are an expert performance-ad copywriter fixing policy violations.

# Brief
Product: {product}
Value proposition: {value_prop}
Tone: {tone}
Creative angle: {angle}
Target format: {format_name} (headline max {headline_max}, body max {body_max})
Policy profile: {policy_profile}

# Original copy (VIOLATES POLICY)
Headline: {orig_headline}
Body: {orig_body}
CTA: {orig_cta}

# Violations to fix
{violations}

# Instructions
Rewrite the ad to fix every violation listed above. Preserve the core
message and value prop — do not change the core message, only fix what
the policy flagged. Keep within the format's character limits.

Return JSON only, no prose. Exact shape:
{{
  "candidates": [
    {{"headline": "...", "body": "...", "cta": "..."}}
  ]
}}
"""


def build_heal_prompt(
    brief: AdBrief, candidate: dict, violations: list[str]
) -> str:
    fmt = get_format(candidate["format"])
    violations_block = "\n".join(f"- {v}" for v in violations)
    return _HEAL_PROMPT.format(
        product=brief.product,
        value_prop=brief.value_prop,
        tone=brief.tone,
        angle=candidate.get("angle", ""),
        format_name=candidate["format"],
        headline_max=fmt.headline_max,
        body_max=fmt.body_max,
        policy_profile=brief.policy_profile,
        orig_headline=candidate["headline"],
        orig_body=candidate["body"],
        orig_cta=candidate["cta"],
        violations=violations_block,
    )


async def heal_candidate(
    candidate: dict,
    *,
    brief: AdBrief,
    violations: list[str],
    provider: LLMProvider,
    max_retries: int,
    check_fn=None,
) -> dict | None:
    """Attempt to rewrite a policy-violating candidate.

    ``check_fn`` is an optional async callable ``(candidate) -> PolicyReport``
    that replaces the built-in literal ``check_copy`` call — used by the
    pipeline to inject the semantic-policy second pass. When omitted, falls
    back to ``check_copy`` alone.

    Returns the healed candidate (with ``healed_from`` and ``heal_attempts``
    metadata attached) or None if healing failed within ``max_retries``.
    """
    fmt = get_format(candidate["format"])
    original = {
        "headline": candidate["headline"],
        "body": candidate["body"],
        "cta": candidate["cta"],
    }
    current = candidate
    current_violations = violations

    for attempt in range(1, max_retries + 1):
        prompt = build_heal_prompt(brief, current, current_violations)
        raw = await provider.generate(prompt, n=1)
        cands = parse_copy_candidates(raw)
        if not cands:
            return None
        fix = cands[0]
        fix_candidate = {
            **fix, "format": candidate["format"], "angle": candidate["angle"],
        }

        if check_fn is not None:
            report = await check_fn(fix_candidate)
        else:
            report = check_copy(
                headline=fix["headline"],
                body=fix["body"],
                cta=fix["cta"],
                format_spec=fmt,
                profile=brief.policy_profile,
                must_include=brief.must_include,
                must_avoid=brief.must_avoid,
            )
        if not report.violations:
            return {
                **fix,
                "format": candidate["format"],
                "angle": candidate["angle"],
                "warnings": report.warnings,
                "healed_from": original,
                "heal_attempts": attempt,
            }
        current = fix_candidate
        current_violations = report.violations

    return None
