"""Second-pass LLM policy check.

The deterministic blocklist in ``policy.py`` catches literal phrases.
This module asks the LLM to catch paraphrases and implied overclaim
that slip through. Opt-in via ``AdBrief.use_semantic_policy``.
"""

from __future__ import annotations

import json
import re

from adclip.llm import LLMProvider
from adclip.schema import AdBrief


_PROFILE_INTENT: dict[str, str] = {
    "default": (
        "Flag copy that implies unverifiable claims, obvious scam signals, "
        "or substantial overclaim on benefits."
    ),
    "crypto": (
        "Flag copy that implies guaranteed returns or profits, elimination "
        "of risk, safety guarantees, or 'get rich quick' framing — including "
        "paraphrases like 'zero risk', 'risk zero', 'no risk', 'pay nothing', "
        "'free money', 'without risk', or 'safe trading'. Educational, "
        "paper-trade, and audit-before-you-commit angles are fine."
    ),
    "health": (
        "Flag copy that implies medical cures, unverified FDA approval, "
        "miracle claims, or 'doctors hate this' framing — including paraphrases."
    ),
    "alcohol": (
        "Flag copy that implies health benefits from alcohol consumption — "
        "including paraphrases like 'heart healthy' or 'detox'."
    ),
    "financial_services": (
        "Flag copy that implies guaranteed credit approval or circumventing "
        "credit review — including paraphrases."
    ),
}


_SEMANTIC_PROMPT = """\
You are a compliance reviewer performing a second-pass semantic check on ad copy.
A literal blocklist already ran; your job is to catch paraphrases it missed.

# Policy profile: {profile}

# Intent to enforce
{intent}

# Copy under review
Headline: {headline}
Body: {body}
CTA: {cta}

# Task
List only semantic violations — paraphrases, synonyms, or implied overclaim
that violate the intent above. Do NOT flag literal phrases already caught by
a blocklist; only catch what slips through. Return an empty list if the copy
is clean.

Return JSON only, no prose. Exact shape:
{{
  "violations": ["short description of each semantic issue"]
}}
"""


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def build_semantic_prompt(brief: AdBrief, candidate: dict) -> str:
    intent = _PROFILE_INTENT.get(
        brief.policy_profile, _PROFILE_INTENT["default"]
    )
    return _SEMANTIC_PROMPT.format(
        profile=brief.policy_profile,
        intent=intent,
        headline=candidate.get("headline", ""),
        body=candidate.get("body", ""),
        cta=candidate.get("cta", ""),
    )


def parse_semantic_response(raw: str) -> list[str]:
    match = _JSON_OBJECT_RE.search(raw)
    if not match:
        raise ValueError(f"No JSON object in semantic response: {raw[:200]}")
    obj = json.loads(match.group(0))
    items = obj.get("violations", [])
    if not isinstance(items, list):
        raise ValueError(f"'violations' must be a list, got: {obj}")
    return [str(x) for x in items]


async def semantic_check(
    candidate: dict, *, brief: AdBrief, provider: LLMProvider
) -> list[str]:
    """Return violation strings (prefixed with 'semantic: ') or an empty list."""
    prompt = build_semantic_prompt(brief, candidate)
    raw = await provider.generate(prompt, n=1)
    items = parse_semantic_response(raw)
    return [f"semantic: {v}" for v in items]
