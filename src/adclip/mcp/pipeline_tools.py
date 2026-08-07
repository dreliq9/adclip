"""MCP tool: adclip_generate_variants (full pipeline)."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from adclip.application import AdclipApplication
from adclip.llm import LLMProvider
from adclip.providers.media import (
    fake_image_provider as _fake_image_fn,
    fake_video_provider as _fake_video_fn,
)


def _resolve_llm(name: str, session) -> LLMProvider:
    """Compatibility wrapper retained for existing internal callers/tests."""

    return AdclipApplication().resolve_llm_provider(name, session=session)


async def _generate_variants_impl(
    brief_json: str,
    *,
    llm_provider: str = "default",
    image_provider: str = "default",
    video_provider: str = "default",
    session=None,
) -> dict:
    return await AdclipApplication().generate_variants_json(
        brief_json,
        llm_provider_name=llm_provider,
        image_provider_name=image_provider,
        video_provider_name=video_provider,
        session=session,
    )


def register(mcp) -> None:
    @mcp.tool()
    async def adclip_generate_variants(
        brief_json: str,
        ctx: Context,
        llm_provider: str = "default",
        image_provider: str = "default",
        video_provider: str = "default",
    ) -> str:
        """Run the full pipeline: copy -> policy -> media -> compose -> render.

        Args:
            brief_json: JSON-encoded AdBrief.
            llm_provider: 'default'/'claude-cli', 'sampling', 'anthropic',
                or 'fake'.
            image_provider: 'default' (fal.ai Flux) or 'fake' (tests).
            video_provider: 'default' (fal.ai) or 'fake' (tests).
        """
        session = ctx.request_context.session
        result = await _generate_variants_impl(
            brief_json,
            llm_provider=llm_provider,
            image_provider=image_provider,
            video_provider=video_provider,
            session=session,
        )
        return json.dumps(result)
