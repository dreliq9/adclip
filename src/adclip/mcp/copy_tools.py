"""MCP tools: copy generation pipeline + standalone policy check.

MCP is an interface adapter over :class:`adclip.application.AdclipApplication`.
Provider and model selection are forwarded without embedding vendor logic here.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from adclip.application import AdclipApplication
from adclip.formats import get_format
from adclip.providers.contracts import TextGenerationProvider
from adclip.policy import check_copy
from adclip.schema import AdBrief


def _get_provider(
    name: str,
    *,
    session=None,
    model: str | None = None,
) -> TextGenerationProvider:
    """Compatibility wrapper around the application provider registry."""

    return AdclipApplication().resolve_text_provider(
        name,
        model=model,
        session=session,
    )


def _filter_pool(pool: list[dict], brief: AdBrief) -> tuple[list[dict], list[dict]]:
    """Compatibility wrapper for the transport-neutral copy policy pass."""

    return AdclipApplication.filter_copy_pool(pool, brief)


async def _generate_copy_impl(
    brief_json: str,
    provider_name: str = "default",
    *,
    model_name: str | None = None,
    session=None,
) -> dict:
    return await AdclipApplication().generate_copy_json(
        brief_json,
        provider_name=provider_name,
        model_name=model_name,
        session=session,
    )


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
        headline=headline,
        body=body,
        cta=cta,
        format_spec=fmt,
        profile=profile,  # type: ignore[arg-type]
        must_include=must_include,
        must_avoid=must_avoid,
    )
    return {
        "ok": True,
        "violations": report.violations,
        "warnings": report.warnings,
    }


def register(mcp) -> None:
    @mcp.tool()
    async def adclip_generate_copy(
        brief_json: str,
        ctx: Context,
        provider: str = "default",
        model: str | None = None,
    ) -> str:
        """Generate, policy-filter, and rank a copy pool.

        ``provider`` and ``model`` are independent. Built-ins include
        claude-cli, sampling, anthropic, openai-compatible, and fake.
        """
        session = ctx.request_context.session
        result = await _generate_copy_impl(
            brief_json,
            provider_name=provider,
            model_name=model,
            session=session,
        )
        return json.dumps(result)

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
        return json.dumps(
            _policy_check_impl(
                headline=headline,
                body=body,
                cta=cta,
                format_name=format_name,
                profile=profile,
                must_include_json=must_include_json,
                must_avoid_json=must_avoid_json,
            )
        )
