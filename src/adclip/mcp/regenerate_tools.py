"""MCP tool: adclip_regenerate (redo one variant: copy, visual, or both)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Literal

from pydantic import ValidationError

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
        p for p in variant_dir.glob(f"{format_name}_*.png")
        if p.name != f"{format_name}.png"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


async def _regenerate_copy(
    vdir: Path, brief: AdBrief, existing_copy: dict,
    *, llm_provider: LLMProvider, pool_size: int = 3,
) -> dict:
    fmt_name = existing_copy["format"]
    angle = existing_copy.get("angle", brief.angles[0])
    fmt = get_format(fmt_name)

    prompt = build_prompt(brief, format_name=fmt_name, angle=angle)
    raw = await llm_provider.generate(prompt, n=pool_size)
    try:
        cands = parse_copy_candidates(raw)
    except ValueError as e:
        return {"ok": False, "error": f"Failed to parse regenerated copy: {e}"}

    cands = [{**c, "format": fmt_name, "angle": angle} for c in cands]

    survivors: list[dict] = []
    for c in cands:
        r = check_copy(
            headline=c["headline"], body=c["body"], cta=c["cta"],
            format_spec=fmt, profile=brief.policy_profile,
            must_include=brief.must_include, must_avoid=brief.must_avoid,
        )
        if not r.violations:
            survivors.append({**c, "warnings": r.warnings})

    if not survivors:
        return {"ok": False, "error": "All regenerated candidates violated policy"}

    winner = rank_pool(survivors, n=1)[0]
    (vdir / "copy.json").write_text(json.dumps(winner, indent=2))
    return {"ok": True, "winner": winner}


def _regenerate_visual(
    vdir: Path, brief: AdBrief, copy: dict,
    *, image_fn: Callable, seed: int | None,
) -> dict:
    fmt_name = copy["format"]
    fmt = get_format(fmt_name)
    if fmt.kind != "static":
        return {
            "ok": False,
            "error": f"Visual regen only supports static formats (got kind={fmt.kind!r})",
        }

    prompt = build_image_prompt(brief, format_name=fmt_name, variant_copy=copy)
    img = image_fn(prompt, format_name=fmt_name, output_dir=str(vdir), seed=seed)
    return {
        "ok": True,
        "image_path": img.local_path,
        "cost_usd": img.cost_usd,
    }


def _recomposite(vdir: Path, root: Path, brief: AdBrief, copy: dict) -> dict:
    fmt_name = copy["format"]
    fmt = get_format(fmt_name)

    if fmt.kind == "text":
        out = vdir / f"{fmt_name}.json"
        out.write_text(json.dumps(copy, indent=2))
        return {"ok": True, "output_path": str(out.relative_to(root))}

    if fmt.kind != "static":
        return {"ok": False, "error": f"Compose unsupported for kind {fmt.kind!r}"}

    bg = _find_raw_background(vdir, fmt_name)
    if bg is None:
        return {
            "ok": False,
            "error": (
                f"No raw background found in {vdir} for {fmt_name!r}; "
                f"regenerate with what='visual' or 'both' first."
            ),
        }

    plan = build_overlay_plan(
        format_name=fmt_name, copy=copy, logo_path=brief.logo_path,
    )
    out = vdir / f"{fmt_name}.png"
    render_static_ad(plan, background=str(bg), output=str(out))
    return {"ok": True, "output_path": str(out.relative_to(root))}


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

    vdir = root / "variants" / variant_id
    if not vdir.is_dir():
        return {"ok": False, "error": f"Variant not found: {variant_id}"}

    brief_path = root / "brief.json"
    if not brief_path.exists():
        return {"ok": False, "error": f"brief.json missing in {campaign_dir}"}

    try:
        brief = AdBrief(**json.loads(brief_path.read_text()))
    except (ValidationError, ValueError, json.JSONDecodeError) as e:
        return {"ok": False, "error": f"brief.json invalid: {e}"}

    copy_path = vdir / "copy.json"
    if not copy_path.exists():
        return {"ok": False, "error": f"copy.json missing in {vdir}"}
    try:
        copy = json.loads(copy_path.read_text())
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"copy.json unreadable: {e}"}

    result: dict = {"ok": True, "variant_id": variant_id, "what": what}
    total_cost = 0.0

    if what in ("copy", "both"):
        if llm_provider is None:
            return {"ok": False, "error": "copy regeneration requires an llm_provider"}
        r = await _regenerate_copy(
            vdir, brief, copy, llm_provider=llm_provider, pool_size=pool_size,
        )
        if not r["ok"]:
            return r
        copy = r["winner"]
        result["copy"] = copy

    if what in ("visual", "both"):
        if image_fn is None:
            return {"ok": False, "error": "visual regeneration requires an image_fn"}
        r = _regenerate_visual(vdir, brief, copy, image_fn=image_fn, seed=seed)
        if not r["ok"]:
            return r
        total_cost += r["cost_usd"]
        result["image_path"] = str(Path(r["image_path"]).relative_to(root))

    comp = _recomposite(vdir, root, brief, copy)
    if not comp["ok"]:
        return comp
    result["output_path"] = comp["output_path"]
    result["total_cost_usd"] = total_cost
    return result


def register(mcp) -> None:
    @mcp.tool()
    async def adclip_regenerate(
        campaign_dir: str,
        variant_id: str,
        what: str = "both",
        llm_provider: str = "default",
        image_provider: str = "default",
        seed: int | None = None,
        pool_size: int = 3,
    ) -> str:
        """Redo one variant's copy, visual, or both. Re-composites after.

        Args:
            campaign_dir: path to the campaign output directory.
            variant_id: e.g. "v01".
            what: 'copy', 'visual', or 'both'.
            llm_provider: copy path provider ('default'/'claude-cli',
                'sampling', 'anthropic', 'fake'). Ignored unless what
                includes 'copy'.
            image_provider: visual path provider ('default' = fal.ai Flux,
                'fake' = test stub). Ignored unless what includes 'visual'.
            seed: optional seed for image gen.
            pool_size: candidates per regen pass for the copy path (top-1
                kept after policy filter and heuristic rank).
        """
        if what not in ("copy", "visual", "both"):
            return json.dumps({
                "ok": False,
                "error": f"Invalid what={what!r}; must be 'copy', 'visual', or 'both'.",
            })

        llm = None
        img_fn = None
        if what in ("copy", "both"):
            from adclip.mcp.pipeline_tools import _resolve_llm
            try:
                llm = _resolve_llm(llm_provider, session=None)
            except RuntimeError as e:
                return json.dumps({"ok": False, "error": str(e)})
        if what in ("visual", "both"):
            from adclip.mcp.pipeline_tools import _fake_image_fn
            if image_provider == "fake":
                img_fn = _fake_image_fn
            else:
                from adclip.image_gen import generate_image as img_fn  # type: ignore

        result = await _regenerate_impl(
            campaign_dir, variant_id,
            what=what, llm_provider=llm, image_fn=img_fn,
            seed=seed, pool_size=pool_size,
        )
        return json.dumps(result)
