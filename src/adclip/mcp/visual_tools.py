"""MCP tool: adclip_generate_visuals (visual-only pipeline, reuses existing copy)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from adclip.campaign import init_campaign_dir, variant_dir, write_manifest
from adclip.compose import build_overlay_plan
from adclip.formats import get_format
from adclip.image_gen import build_image_prompt
from adclip.render import render_static_ad
from adclip.schema import AdBrief


def _validate_copies(copies: list[dict]) -> str | None:
    if not isinstance(copies, list) or not copies:
        return "copies must be a non-empty list of dicts"
    required = {"headline", "body", "cta", "format"}
    for i, c in enumerate(copies):
        if not isinstance(c, dict):
            return f"copies[{i}] is not a dict"
        missing = required - c.keys()
        if missing:
            return f"copies[{i}] missing required fields: {sorted(missing)}"
    return None


def _generate_visuals_impl(
    brief_json: str,
    copies_json: str,
    *,
    image_fn: Callable | None = None,
) -> dict:
    try:
        brief = AdBrief(**json.loads(brief_json))
    except (ValidationError, ValueError, json.JSONDecodeError) as e:
        return {"ok": False, "error": f"brief_json invalid: {e}"}

    try:
        copies = json.loads(copies_json)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"copies_json invalid: {e}"}

    err = _validate_copies(copies)
    if err:
        return {"ok": False, "error": err}

    if image_fn is None:
        from adclip.image_gen import generate_image as image_fn  # type: ignore

    root = init_campaign_dir(brief)
    entries: list[dict] = []
    total_cost = 0.0

    for i, copy in enumerate(copies, start=1):
        vid = f"v{i:02d}"
        vdir = variant_dir(brief, vid)
        (vdir / "copy.json").write_text(json.dumps(copy, indent=2))

        try:
            fmt = get_format(copy["format"])
        except KeyError as e:
            return {"ok": False, "error": str(e)}

        if fmt.kind == "text":
            out = vdir / f"{copy['format']}.json"
            out.write_text(json.dumps(copy, indent=2))
            entries.append({
                "variant_id": vid,
                "format": copy["format"],
                "path": f"variants/{vid}/{copy['format']}.json",
            })
            continue

        if fmt.kind == "static":
            prompt = build_image_prompt(
                brief, format_name=copy["format"], variant_copy=copy,
            )
            img = image_fn(
                prompt, format_name=copy["format"], output_dir=str(vdir), seed=i,
            )
            total_cost += img.cost_usd

            plan = build_overlay_plan(
                format_name=copy["format"], copy=copy, logo_path=brief.logo_path,
            )
            final = vdir / f"{copy['format']}.png"
            render_static_ad(plan, background=img.local_path, output=str(final))
            entries.append({
                "variant_id": vid,
                "format": copy["format"],
                "path": f"variants/{vid}/{copy['format']}.png",
            })
            continue

        # video
        entries.append({
            "variant_id": vid,
            "format": copy["format"],
            "path": None,
            "note": "video formats not yet implemented in pipeline",
        })

    write_manifest(brief, entries=entries, cost_usd=total_cost)
    return {
        "ok": True,
        "entries": entries,
        "total_cost_usd": total_cost,
        "campaign_dir": str(Path(brief.output_dir).resolve()),
    }


def register(mcp) -> None:
    @mcp.tool()
    def adclip_generate_visuals(
        brief_json: str,
        copies_json: str,
        image_provider: str = "default",
    ) -> str:
        """Produce visuals for an existing set of copies — no LLM call.

        Typical workflow: call adclip_generate_copy first to iterate on
        copy cheaply, then pass the selected winners here to materialize
        the full campaign (images + overlays + manifest).

        Args:
            brief_json: JSON-encoded AdBrief.
            copies_json: JSON-encoded list of copy dicts. Each must have
                ``headline``, ``body``, ``cta``, ``format``, and
                typically ``angle``.
            image_provider: 'default' (fal.ai Flux) or 'fake' (tests).
        """
        image_fn = None
        if image_provider == "fake":
            from adclip.mcp.pipeline_tools import _fake_image_fn
            image_fn = _fake_image_fn

        result = _generate_visuals_impl(
            brief_json, copies_json, image_fn=image_fn,
        )
        return json.dumps(result)
