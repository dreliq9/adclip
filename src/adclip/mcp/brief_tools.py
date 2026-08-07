"""MCP tools: brief validation, format listing, cost estimation."""

from __future__ import annotations

import json

from adclip.application import AdclipApplication


def _brief_validate_impl(brief_json: str) -> dict:
    return AdclipApplication().validate_brief_json(brief_json)


def _list_formats_impl() -> dict:
    return AdclipApplication.list_formats()


def _estimate_cost_impl(brief_json: str) -> dict:
    return AdclipApplication().estimate_cost_json(brief_json)


def register(mcp) -> None:
    @mcp.tool()
    def adclip_brief_validate(brief_json: str) -> str:
        """Validate an AdBrief JSON payload against schema and format catalog.

        Args:
            brief_json: JSON-encoded AdBrief object.

        Returns:
            JSON with ok/error and the parsed brief (if valid).
        """
        return json.dumps(_brief_validate_impl(brief_json))

    @mcp.tool()
    def adclip_list_formats() -> str:
        """Enumerate all supported ad formats with their specs (char limits, dims)."""
        return json.dumps(_list_formats_impl())

    @mcp.tool()
    def adclip_estimate_cost(brief_json: str) -> str:
        """Estimate USD cost for running a brief (LLM + fal image + fal video).

        Args:
            brief_json: JSON-encoded AdBrief object.
        """
        return json.dumps(_estimate_cost_impl(brief_json))
