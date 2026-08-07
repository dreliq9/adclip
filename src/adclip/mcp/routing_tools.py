"""MCP tools for media route discovery and recommendation."""

from __future__ import annotations

import json

from adclip.application import AdclipApplication


def register(mcp) -> None:
    @mcp.tool()
    def adclip_list_media_routes(modality: str | None = None) -> str:
        """List image/video task routes, primary models, and ordered fallbacks."""
        return json.dumps(AdclipApplication.list_media_routes(modality))

    @mcp.tool()
    def adclip_recommend_media_route(
        modality: str,
        text_heavy: bool = False,
        reference_images: int = 0,
        reference_media: int = 0,
        existing_video: bool = False,
        vector_output: bool = False,
        premium: bool = False,
        high_volume: bool = False,
        draft: bool = False,
        multi_shot: bool = False,
        brand_control: bool = False,
    ) -> str:
        """Recommend a route from explicit creative requirements."""
        return json.dumps(
            AdclipApplication.recommend_media_route(
                modality,
                text_heavy=text_heavy,
                reference_images=reference_images,
                reference_media=reference_media,
                existing_video=existing_video,
                vector_output=vector_output,
                premium=premium,
                high_volume=high_volume,
                draft=draft,
                multi_shot=multi_shot,
                brand_control=brand_control,
            )
        )
