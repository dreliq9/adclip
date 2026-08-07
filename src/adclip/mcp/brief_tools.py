"""MCP tools: brief validation, format listing, and routed cost estimation."""

from __future__ import annotations

import json

from adclip.application import AdclipApplication


def _brief_validate_impl(brief_json: str) -> dict:
    return AdclipApplication().validate_brief_json(brief_json)


def _list_formats_impl() -> dict:
    return AdclipApplication.list_formats()


def _estimate_cost_impl(
    brief_json: str,
    *,
    image_route: str | None = None,
    image_model: str | None = None,
    video_route: str | None = None,
    video_model: str | None = None,
) -> dict:
    return AdclipApplication().estimate_cost_json(
        brief_json,
        image_route_name=image_route,
        image_model_name=image_model,
        video_route_name=video_route,
        video_model_name=video_model,
    )


def register(mcp) -> None:
    @mcp.tool()
    def adclip_brief_validate(brief_json: str) -> str:
        """Validate an AdBrief JSON payload."""
        return json.dumps(_brief_validate_impl(brief_json))

    @mcp.tool()
    def adclip_list_formats() -> str:
        """Enumerate supported ad formats and their specs."""
        return json.dumps(_list_formats_impl())

    @mcp.tool()
    def adclip_estimate_cost(
        brief_json: str,
        image_route: str = "default",
        image_model: str | None = None,
        video_route: str = "default",
        video_model: str | None = None,
    ) -> str:
        """Estimate the selected route primaries without executing providers."""
        return json.dumps(
            _estimate_cost_impl(
                brief_json,
                image_route=image_route,
                image_model=image_model,
                video_route=video_route,
                video_model=video_model,
            )
        )
