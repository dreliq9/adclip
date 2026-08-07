"""MCP tool: adclip_regenerate (redo one variant: copy, visual, or both)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Literal

from pydantic import ValidationError

from adclip.application import AdclipApplication
from adclip.compose import build_overlay_plan
from adclip.copy import build_prompt
from adclip.formats import get_format
from adclip.image_gen import build_image_prompt
from adclip.llm import LLMProvider, parse_copy_candidates
from adclip.policy import check_copy
from adclip.render import render_static_ad
from adclip.schema import AdBrief
from adclip.scoring import rank_pool


What = Literal["copy", "visual", "both"]


def _find_raw_background(variant_dir: Path, format_name: str) -> Path | None:
    candidates = [
        path
        for path in variant_dir.glob(f"{format_name}_*.png")
        if path.name != f"{format_name}.png"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


async def _regenerate_copy(
    variant_dir: Path,
    brief: AdBrief,
    existing_copy: dict,
    *,
    llm_provider: LLMProvider,
    pool_size: int = 3,
) -> dict:
    format_name = existing_copy["format"]
    angle = existing_copy.get("angle", brief.angles[0])
    format_spec = get_format(format_name)

    prompt = build_prompt(brief, format_name=format_name, angle=angle)
    raw = await llm_provider.generate(prompt, n=pool_size)
    try:
        candidates = parse_copy_candidates(raw)
    except ValueError as exc:
        return {"ok": False, "error": f"Failed to parse regenerated copy: {exc}"}

    candidates = [
        {**candidate, "format": format_name, "angle": angle}
        for candidate in candidates
    ]
    survivors: list[dict] = []
    for candidate in candidates:
        report = check_copy(
            headline=candidate["headline"],
            body=candidate["body"],
            cta=candidate["cta"],
            format_spec=format_spec,
            profile=brief.policy_profile,
            must_include=brief.must_include,
            must_avoid=brief.must_avoid,
        )
        if not report.violations:
            survivors.append({**candidate, "warnings": report.warnings})

    if not survivors:
        return {"ok": False, "error": "All regenerated candidates violated policy"}

    winner = rank_pool(survivors, n=1)[0]
    (variant_dir / "copy.json").write_text(json.dumps(winner, indent=2))
    return {"ok": True, "winner": winner}


def _regenerate_visual(
    variant_dir: Path,
    brief: AdBrief,
    copy: dict,
    *,
    image_fn: Callable,
    seed: int | None,
) -> dict:
    format_name = copy["format"]
    format_spec = get_format(format_name)
    if format_spec.kind != "static":
        return {
            "ok": False,
            "error": (
                "Visual regen only supports static formats "
                f"(got kind={format_spec.kind!r})"
            ),
        }

    prompt = build_image_prompt(
        brief,
        format_name=format_name,
        variant_copy=copy,
    )
    image = image_fn(
        prompt,
        format_name=format_name,
        output_dir=str(variant_dir),
        seed=seed,
    )
    return {
        "ok": True,
        "image_path": image.local_path,
        "cost_usd": image.cost_usd,
    }


def _recomposite(
    variant_dir: Path,
    root: Path,
    brief: AdBrief,
    copy: dict,
) -> dict:
    format_name = copy["format"]
    format_spec = get_format(format_name)

    if format_spec.kind == "text":
        output = variant_dir / f"{format_name}.json"
        output.write_text(json.dumps(copy, indent=2))
        return {"ok": True, "output_path": str(output.relative_to(root))}

    if format_spec.kind != "static":
        return {
            "ok": False,
            "error": f"Compose unsupported for kind {format_spec.kind!r}",
        }

    background = _find_raw_background(variant_dir, format_name)
    if background is None:
        return {
            "ok": False,
            "error": (
                f"No raw background found in {variant_dir} for {format_name!r}; "
                "regenerate with what='visual' or 'both' first."
            ),
        }

    plan = build_overlay_plan(
        format_name=format_name,
        copy=copy,
        logo_path=brief.logo_path,
    )
    output = variant_dir / f"{format_name}.png"
    render_static_ad(plan, background=str(background), output=str(output))
    return {"ok": True, "output_path": str(output.relative_to(root))}


async def _regenerate_impl(
    campaign_dir: str,
    variant_id: str,
    *,
    what: What = "both",
    llm_provider: LLMProvider | None = None,
    image_fn: Callable | None = None,
    seed: int | None = None,
    pool_size: int = 3,
) -> dict:
    root = Path(campaign_dir)
    if not root.is_dir():
        return {"ok": False, "error": f"Campaign dir not found: {campaign_dir}"}

    variant_dir = root / "variants" / variant_id
    if not variant_dir.is_dir():
        return {"ok": False, "error": f"Variant not found: {variant_id}"}

    brief_path = root / "brief.json"
    if not brief_path.exists():
        return {"ok": False, "error": f"brief.json missing in {campaign_dir}"}

    try:
        brief = AdBrief(**json.loads(brief_path.read_text()))
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"brief.json invalid: {exc}"}

    copy_path = variant_dir / "copy.json"
    if not copy_path.exists():
        return {"ok": False, "error": f"copy.json missing in {variant_dir}"}
    try:
        copy = json.loads(copy_path.read_text())
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"copy.json unreadable: {exc}"}

    result: dict = {"ok": True, "variant_id": variant_id, "what": what}
    total_cost = 0.0

    if what in ("copy", "both"):
        if llm_provider is None:
            return {"ok": False, "error": "copy regeneration requires an llm_provider"}
        regenerated = await _regenerate_copy(
            variant_dir,
            brief,
            copy,
            llm_provider=llm_provider,
            pool_size=pool_size,
        )
        if not regenerated["ok"]:
            return regenerated
        copy = regenerated["winner"]
        result["copy"] = copy

    if what in ("visual", "both"):
        if image_fn is None:
            return {"ok": False, "error": "visual regeneration requires an image_fn"}
        regenerated = _regenerate_visual(
            variant_dir,
            brief,
            copy,
            image_fn=image_fn,
            seed=seed,
        )
        if not regenerated["ok"]:
            return regenerated
        total_cost += regenerated["cost_usd"]
        result["image_path"] = str(
            Path(regenerated["image_path"]).relative_to(root)
        )

    composite = _recomposite(variant_dir, root, brief, copy)
    if not composite["ok"]:
        return composite
    result["output_path"] = composite["output_path"]
    result["total_cost_usd"] = total_cost
    return result


def register(mcp) -> None:
    @mcp.tool()
    async def adclip_regenerate(
        campaign_dir: str,
        variant_id: str,
        what: str = "both",
        llm_provider: str = "default",
        llm_model: str | None = None,
        image_provider: str = "default",
        image_model: str | None = None,
        seed: int | None = None,
        pool_size: int = 3,
    ) -> str:
        """Redo one variant's copy, static visual, or both.

        Provider and model are independently selectable for each regenerated
        modality. Existing provider arguments remain backward compatible.
        """
        if what not in ("copy", "visual", "both"):
            return json.dumps({
                "ok": False,
                "error": (
                    f"Invalid what={what!r}; must be 'copy', 'visual', or 'both'."
                ),
            })

        app = AdclipApplication()
        text_provider = None
        text_selection = None
        image_binding = None
        try:
            if what in ("copy", "both"):
                text_provider, text_selection = (
                    app.resolve_text_provider_with_selection(
                        llm_provider,
                        model=llm_model,
                    )
                )
            if what in ("visual", "both"):
                from adclip.providers.media import resolve_image_provider

                image_binding = resolve_image_provider(
                    image_provider,
                    model=image_model,
                    policy=app.runtime_policy,
                )
        except (RuntimeError, ValueError) as exc:
            return json.dumps({"ok": False, "error": str(exc)})

        result = await _regenerate_impl(
            campaign_dir,
            variant_id,
            what=what,  # type: ignore[arg-type]
            llm_provider=text_provider,
            image_fn=image_binding,
            seed=seed,
            pool_size=pool_size,
        )
        if result.get("ok"):
            models: dict[str, dict[str, str | None]] = {}
            if text_selection is not None:
                models["text"] = text_selection.as_dict()
            if image_binding is not None:
                models["image"] = image_binding.as_dict()
            result["models"] = models
        return json.dumps(result)
