"""MCP tools: brief validation, format listing, cost estimation."""

from __future__ import annotations

import json

from pydantic import ValidationError

from adclip.cost import estimate_cost
from adclip.formats import FORMATS
from adclip.schema import AdBrief


def _brief_validate_impl(brief_json: str) -> dict:
    try:
        data = json.loads(brief_json)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Invalid JSON: {e}"}
    try:
        brief = AdBrief(**data)
    except ValidationError as e:
        return {"ok": False, "error": str(e)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "brief": brief.model_dump()}


def _list_formats_impl() -> dict:
    return {
        "formats": [
            {
                "name": spec.name,
                "aspect": spec.aspect,
                "width": spec.width,
                "height": spec.height,
                "kind": spec.kind,
                "headline_max": spec.headline_max,
                "body_max": spec.body_max,
                "rsa_max_headlines": spec.rsa_max_headlines,
                "rsa_max_descriptions": spec.rsa_max_descriptions,
            }
            for spec in FORMATS.values()
        ]
    }


def _estimate_cost_impl(brief_json: str) -> dict:
    try:
        data = json.loads(brief_json)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Invalid JSON: {e}"}
    try:
        brief = AdBrief(**data)
    except (ValidationError, ValueError) as e:
        return {"ok": False, "error": str(e)}
    est = estimate_cost(brief)
    return {
        "ok": True,
        "llm_cost_usd": est.llm_cost_usd,
        "image_cost_usd": est.image_cost_usd,
        "video_cost_usd": est.video_cost_usd,
        "total_usd": est.total_usd,
        "over_budget": est.over_budget,
        "budget_usd": est.budget_usd,
        "breakdown": est.breakdown,
    }


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
