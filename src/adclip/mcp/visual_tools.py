"""MCP tool: adclip_generate_visuals (visual-only pipeline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from adclip.application import AdclipApplication
from adclip.campaign import init_campaign_dir, variant_dir, write_manifest
from adclip.compose import build_overlay_plan
from adclip.formats import get_format
from adclip.image_gen import build_image_prompt
from adclip.providers.media import resolve_image_provider, resolve_video_provider
from adclip.render import render_static_ad, render_video_ad
from adclip.schema import AdBrief


def _validate_copies(copies: list[dict]) -> str | None:
    if not isinstance(copies, list) or not copies:
        return "copies must be a non-empty list of dicts"
    required = {"headline", "body", "cta", "format"}
    for index, copy in enumerate(copies):
        if not isinstance(copy, dict):
            return f"copies[{index}] is not a dict"
        missing = required - copy.keys()
        if missing:
            return f"copies[{index}] missing required fields: {sorted(missing)}"
    return None


def _generate_visuals_impl(
    brief_json: str,
    copies_json: str,
    *,
    image_fn: Callable | None = None,
    video_fn: Callable | None = None,
    models: dict[str, object] | None = None,
) -> dict:
    try:
        brief = AdBrief(**json.loads(brief_json))
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"brief_json invalid: {exc}"}

    try:
        copies = json.loads(copies_json)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"copies_json invalid: {exc}"}

    error = _validate_copies(copies)
    if error:
        return {"ok": False, "error": error}

    if image_fn is None:
        from adclip.image_gen import generate_image as image_fn  # type: ignore
    if video_fn is None:
        from adclip.video_gen import generate_ad_clip as video_fn  # type: ignore

    root = init_campaign_dir(brief)
    entries: list[dict] = []
    total_cost = 0.0

    for index, copy in enumerate(copies, start=1):
        variant_id = f"v{index:02d}"
        directory = variant_dir(brief, variant_id)
        (directory / "copy.json").write_text(json.dumps(copy, indent=2))

        try:
            format_spec = get_format(copy["format"])
        except KeyError as exc:
            return {"ok": False, "error": str(exc)}

        if format_spec.kind == "text":
            output = directory / f"{copy['format']}.json"
            output.write_text(json.dumps(copy, indent=2))
            entries.append({
                "variant_id": variant_id,
                "format": copy["format"],
                "path": f"variants/{variant_id}/{copy['format']}.json",
            })
            continue

        prompt = build_image_prompt(
            brief,
            format_name=copy["format"],
            variant_copy=copy,
        )

        if format_spec.kind == "static":
            image = image_fn(
                prompt,
                format_name=copy["format"],
                output_dir=str(directory),
                seed=index,
            )
            total_cost += image.cost_usd
            plan = build_overlay_plan(
                format_name=copy["format"],
                copy=copy,
                logo_path=brief.logo_path,
            )
            output = directory / f"{copy['format']}.png"
            render_static_ad(plan, background=image.local_path, output=str(output))
            entries.append({
                "variant_id": variant_id,
                "format": copy["format"],
                "path": f"variants/{variant_id}/{copy['format']}.png",
            })
            continue

        clip = video_fn(
            prompt,
            format_name=copy["format"],
            output_dir=str(directory),
            seed=index,
        )
        total_cost += clip.cost_usd
        plan = build_overlay_plan(
            format_name=copy["format"],
            copy=copy,
            logo_path=brief.logo_path,
        )
        output = directory / f"{copy['format']}.mp4"
        render_video_ad(plan, background=clip.local_path, output=str(output))
        entries.append({
            "variant_id": variant_id,
            "format": copy["format"],
            "path": f"variants/{variant_id}/{copy['format']}.mp4",
        })

    write_manifest(brief, entries=entries, cost_usd=total_cost, models=models)
    result: dict[str, object] = {
        "ok": True,
        "entries": entries,
        "total_cost_usd": total_cost,
        "campaign_dir": str(Path(brief.output_dir).resolve()),
    }
    if models:
        result["models"] = models
    return result


def register(mcp) -> None:
    @mcp.tool()
    def adclip_generate_visuals(
        brief_json: str,
        copies_json: str,
        image_route: str = "default",
        image_provider: str = "default",
        image_model: str | None = None,
        video_route: str = "default",
        video_provider: str = "default",
        video_model: str | None = None,
    ) -> str:
        """Produce routed visuals for existing copy without a text-model call."""
        try:
            copies = json.loads(copies_json)
        except json.JSONDecodeError:
            return json.dumps(_generate_visuals_impl(brief_json, copies_json))
        error = _validate_copies(copies)
        if error:
            return json.dumps({"ok": False, "error": error})

        try:
            kinds = {get_format(copy["format"]).kind for copy in copies}
        except KeyError as exc:
            return json.dumps({"ok": False, "error": str(exc)})

        app = AdclipApplication()
        image_binding = None
        video_binding = None
        try:
            if "static" in kinds:
                image_binding = resolve_image_provider(
                    image_provider,
                    model=image_model,
                    route=image_route,
                    policy=app.runtime_policy,
                )
            if "video" in kinds:
                video_binding = resolve_video_provider(
                    video_provider,
                    model=video_model,
                    route=video_route,
                    policy=app.runtime_policy,
                )
        except (RuntimeError, ValueError) as exc:
            return json.dumps({"ok": False, "error": str(exc)})

        models: dict[str, object] = {}
        if image_binding is not None:
            models["image"] = image_binding.provenance()
        if video_binding is not None:
            models["video"] = video_binding.provenance()

        result = _generate_visuals_impl(
            brief_json,
            copies_json,
            image_fn=image_binding,
            video_fn=video_binding,
            models=models,
        )
        return json.dumps(result)
