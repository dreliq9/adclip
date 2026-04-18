"""MCP tools: copy generation pipeline + standalone policy check."""

from __future__ import annotations

import json

from pydantic import ValidationError

from adclip.copy import generate_copy_pool
from adclip.formats import get_format
from adclip.llm import FakeLLMProvider, default_provider
from adclip.policy import check_copy
from adclip.schema import AdBrief
from adclip.scoring import rank_pool


def _get_provider(name: str):
    if name == "fake":
        return FakeLLMProvider()
    if name == "anthropic" or name == "default":
        return default_provider()
    raise ValueError(f"Unknown provider: {name}")


def _filter_pool(pool: list[dict], brief: AdBrief) -> tuple[list[dict], list[dict]]:
    """Split pool into (survivors, rejected) via policy checks."""
    survivors: list[dict] = []
    rejected: list[dict] = []
    for cand in pool:
        fmt = get_format(cand["format"])
        report = check_copy(
            headline=cand["headline"],
            body=cand["body"],
            cta=cand["cta"],
            format_spec=fmt,
            profile=brief.policy_profile,
            must_include=brief.must_include,
            must_avoid=brief.must_avoid,
        )
        cand_out = {**cand, "warnings": report.warnings}
        if report.violations:
            rejected.append({**cand_out, "violations": report.violations})
        else:
            survivors.append(cand_out)
    return survivors, rejected


def _generate_copy_impl(brief_json: str, provider_name: str = "default") -> dict:
    try:
        brief = AdBrief(**json.loads(brief_json))
    except (ValidationError, ValueError, json.JSONDecodeError) as e:
        return {"ok": False, "error": str(e)}

    provider = _get_provider(provider_name)
    pool = generate_copy_pool(brief, provider=provider)
    survivors, rejected = _filter_pool(pool, brief)
    winners = rank_pool(survivors, n=brief.variants, per_bucket=True)
    return {
        "ok": True,
        "winners": winners,
        "rejected": rejected,
        "pool": pool,
    }


def _policy_check_impl(
    *,
    headline: str,
    body: str,
    cta: str,
    format_name: str,
    profile: str,
    must_include_json: str,
    must_avoid_json: str,
) -> dict:
    try:
        fmt = get_format(format_name)
    except KeyError as e:
        return {"ok": False, "error": str(e)}
    try:
        must_include = json.loads(must_include_json)
        must_avoid = json.loads(must_avoid_json)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Bad JSON array: {e}"}

    report = check_copy(
        headline=headline, body=body, cta=cta,
        format_spec=fmt, profile=profile,  # type: ignore[arg-type]
        must_include=must_include, must_avoid=must_avoid,
    )
    return {
        "ok": True,
        "violations": report.violations,
        "warnings": report.warnings,
    }


def register(mcp) -> None:
    @mcp.tool()
    def adclip_generate_copy(brief_json: str, provider: str = "default") -> str:
        """Generate copy pool, filter via policy, return top-ranked winners.

        Args:
            brief_json: JSON-encoded AdBrief.
            provider: 'default' (Anthropic) or 'fake' (tests).
        """
        return json.dumps(_generate_copy_impl(brief_json, provider_name=provider))

    @mcp.tool()
    def adclip_policy_check(
        headline: str,
        body: str,
        cta: str,
        format_name: str,
        profile: str = "default",
        must_include_json: str = "[]",
        must_avoid_json: str = "[]",
    ) -> str:
        """Dry-run policy check against copy without generating anything."""
        return json.dumps(_policy_check_impl(
            headline=headline, body=body, cta=cta,
            format_name=format_name, profile=profile,
            must_include_json=must_include_json,
            must_avoid_json=must_avoid_json,
        ))
