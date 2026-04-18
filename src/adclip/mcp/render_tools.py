"""MCP tool: adclip_render_variant (re-render one variant, no fal spend)."""

from __future__ import annotations

import json
from pathlib import Path

from adclip.compose import build_overlay_plan
from adclip.formats import get_format
from adclip.render import render_static_ad


def _find_raw_background(variant_dir: Path, format_name: str) -> Path | None:
    """Locate a raw image background written by image_gen for this format.

    image_gen writes ``{format_name}_{seed}.png`` (e.g. ``meta_feed_4x5_1.png``).
    The composed output is ``{format_name}.png`` — excluded from the match.
    Returns the most recently modified candidate, or None.
    """
    candidates = [
        p for p in variant_dir.glob(f"{format_name}_*.png")
        if p.name != f"{format_name}.png"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _render_variant_impl(
    campaign_dir: str,
    variant_id: str,
    *,
    format_name: str | None = None,
    background: str | None = None,
) -> dict:
    root = Path(campaign_dir)
    if not root.is_dir():
        return {"ok": False, "error": f"Campaign dir not found: {campaign_dir}"}

    vdir = root / "variants" / variant_id
    if not vdir.is_dir():
        return {"ok": False, "error": f"Variant not found: {variant_id}"}

    copy_path = vdir / "copy.json"
    if not copy_path.exists():
        return {"ok": False, "error": f"copy.json missing in {vdir}"}

    try:
        copy = json.loads(copy_path.read_text())
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"copy.json unreadable: {e}"}

    fmt_name = format_name or copy.get("format")
    if not fmt_name:
        return {"ok": False, "error": "format_name not provided and missing from copy.json"}

    try:
        fmt = get_format(fmt_name)
    except KeyError as e:
        return {"ok": False, "error": str(e)}

    logo_path: str | None = None
    brief_path = root / "brief.json"
    if brief_path.exists():
        try:
            logo_path = json.loads(brief_path.read_text()).get("logo_path")
        except json.JSONDecodeError:
            pass

    if fmt.kind == "text":
        out = vdir / f"{fmt_name}.json"
        out.write_text(json.dumps(copy, indent=2))
        return {
            "ok": True,
            "variant_id": variant_id,
            "format": fmt_name,
            "output_path": str(out.relative_to(root)),
            "kind": "text",
        }

    if fmt.kind == "video":
        return {
            "ok": False,
            "error": f"Video format {fmt_name!r} not yet supported by render_variant",
        }

    # static
    if background:
        bg_path = Path(background)
        if not bg_path.exists():
            return {"ok": False, "error": f"Background not found: {background}"}
        try:
            resolved = bg_path.resolve()
            resolved.relative_to(root.resolve())
        except (ValueError, OSError, RuntimeError):
            return {
                "ok": False,
                "error": (
                    f"Background must live inside campaign_dir "
                    f"({campaign_dir!r}); got {background!r}"
                ),
            }
        bg_path = resolved
    else:
        found = _find_raw_background(vdir, fmt_name)
        if found is None:
            return {
                "ok": False,
                "error": (
                    f"No raw background image found in {vdir} for format "
                    f"{fmt_name!r}. Pass background=<path> or run "
                    f"adclip_generate_variants first."
                ),
            }
        bg_path = found

    plan = build_overlay_plan(format_name=fmt_name, copy=copy, logo_path=logo_path)
    out = vdir / f"{fmt_name}.png"
    render_static_ad(plan, background=str(bg_path), output=str(out))

    return {
        "ok": True,
        "variant_id": variant_id,
        "format": fmt_name,
        "output_path": str(out.relative_to(root)),
        "background_used": str(bg_path.relative_to(root)) if bg_path.is_relative_to(root) else str(bg_path),
        "kind": "static",
    }


def register(mcp) -> None:
    @mcp.tool()
    def adclip_render_variant(
        campaign_dir: str,
        variant_id: str,
        format_name: str | None = None,
        background: str | None = None,
    ) -> str:
        """Re-render one variant using its existing copy.json and raw background.

        No LLM call, no image-gen spend. Use after hand-editing copy.json,
        or to render a variant into an additional format using a
        user-supplied background image.

        Args:
            campaign_dir: path to the campaign output directory.
            variant_id: e.g. "v01".
            format_name: ad format to render. Defaults to the variant's
                original format (from copy.json).
            background: optional override path to a raw background image.
                If omitted, the most recent ``{format_name}_*.png`` in the
                variant dir is used.
        """
        return json.dumps(_render_variant_impl(
            campaign_dir, variant_id,
            format_name=format_name, background=background,
        ))
