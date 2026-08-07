"""MCP tool: adclip_generate_variants (full pipeline)."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from adclip.application import AdclipApplication
from adclip.providers.contracts import TextGenerationProvider
from adclip.providers.media import (
    fake_image_provider as _fake_image_fn,
    fake_video_provider as _fake_video_fn,
)


def _resolve_llm(
    name: str,
    session,
    model: str | None = None,
) -> TextGenerationProvider:
    """Compatibility wrapper retained for existing internal callers/tests."""

    return AdclipApplication().resolve_text_provider(
        name,
        model=model,
        session=session,
    )


async def _generate_variants_impl(
    brief_json: str,
    *,
    llm_provider: str = "default",
    llm_model: str | None = None,
    image_route: str | None = None,
    image_provider: str = "default",
    image_model: str | None = None,
    video_route: str | None = None,
    video_provider: str = "default",
    video_model: str | None = None,
    session=None,
) -> dict:
    return await AdclipApplication().generate_variants_json(
        brief_json,
        llm_provider_name=llm_provider,
        llm_model_name=llm_model,
        image_route_name=image_route,
        image_provider_name=image_provider,
        image_model_name=image_model,
        video_route_name=video_route,
        video_provider_name=video_provider,
        video_model_name=video_model,
        session=session,
    )


def register(mcp) -> None:
    @mcp.tool()
    async def adclip_generate_variants(
        brief_json: str,
        ctx: Context,
        llm_provider: str = "default",
        llm_model: str | None = None,
        image_route: str = "default",
        image_provider: str = "default",
        image_model: str | None = None,
        video_route: str = "default",
        video_provider: str = "default",
        video_model: str | None = None,
    ) -> str:
        """Run copy -> policy -> routed media -> compose -> render.

        Routes select task-appropriate defaults; explicit provider/model values
        remain authoritative overrides.
        """
        session = ctx.request_context.session
        result = await _generate_variants_impl(
            brief_json,
            llm_provider=llm_provider,
            llm_model=llm_model,
            image_route=image_route,
            image_provider=image_provider,
            image_model=image_model,
            video_route=video_route,
            video_provider=video_provider,
            video_model=video_model,
            session=session,
        )
        return json.dumps(result)
