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
        vdir = variant_dir(brief, variant_id)
        (vdir / "copy.json").write_text(json.dumps(copy, indent=2))

        try:
            fmt = get_format(copy["format"])
        except KeyError as exc:
            return {"ok": False, "error": str(exc)}

        if fmt.kind == "text":
            output = vdir / f"{copy['format']}.json"
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
        if fmt.kind == "static":
            image = image_fn(
                prompt,
                format_name=copy["format"],
                output_dir=str(vdir),
                seed=index,
            )
            total_cost += image.cost_usd
            plan = build_overlay_plan(
                format_name=copy["format"],
                copy=copy,
                logo_path=brief.logo_path,
            )
            final = vdir / f"{copy['format']}.png"
            render_static_ad(plan, background=image.local_path, output=str(final))
            entries.append({
                "variant_id": variant_id,
                "format": copy["format"],
                "path": f"variants/{variant_id}/{copy['format']}.png",
            })
            continue

        clip = video_fn(
            prompt,
            format_name=copy["format"],
            output_dir=str(vdir),
            seed=index,
        )
        total_cost += clip.cost_usd
        plan = build_overlay_plan(
            format_name=copy["format"],
            copy=copy,
            logo_path=brief.logo_path,
        )
        final = vdir / f"{copy['format']}.mp4"
        render_video_ad(plan, background=clip.local_path, output=str(final))
        entries.append({
            "variant_id": variant_id,
            "format": copy["format"],
            "path": f"variants/{variant_id}/{copy['format']}.mp4",
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
        image_model: str | None = None,
        video_provider: str = "default",
        video_model: str | None = None,
    ) -> str:
        """Produce visuals for selected copy without another text-model call.

        Image and video provider/model pairs are selected independently and
        follow the same environment/runtime policy as the full pipeline.
        """
        app = AdclipApplication()
        try:
            copies = json.loads(copies_json)
            format_kinds = {
                get_format(copy["format"]).kind
                for copy in copies
                if isinstance(copy, dict) and "format" in copy
            }
            image_binding = None
            if "static" in format_kinds:
                from adclip.providers.media import resolve_image_provider

                image_binding = resolve_image_provider(
                    image_provider,
                    model=image_model,
                    policy=app.runtime_policy,
                )
            video_binding = None
            if "video" in format_kinds:
                from adclip.providers.media import resolve_video_provider

                video_binding = resolve_video_provider(
                    video_provider,
                    model=video_model,
                    policy=app.runtime_policy,
                )
        except (ValueError, RuntimeError, json.JSONDecodeError, KeyError) as exc:
            return json.dumps({"ok": False, "error": str(exc)})

        result = _generate_visuals_impl(
            brief_json,
            copies_json,
            image_fn=image_binding,
            video_fn=video_binding,
        )
        if result.get("ok"):
            models: dict[str, dict[str, str | None]] = {}
            if image_binding is not None:
                models["image"] = image_binding.as_dict()
            if video_binding is not None:
                models["video"] = video_binding.as_dict()
            result["models"] = models
        return json.dumps(result)
