"""MCP tool: adclip_export_dco (export Meta DCO modular components)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from adclip.formats import get_format


def _aspect_slug(aspect: str) -> str:
    """'1:1' -> '1x1', '1.91:1' -> '1.91x1', 'text' -> 'text'."""
    return aspect.replace(":", "x")


def _dedup_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _export_dco_impl(campaign_dir: str) -> dict:
    root = Path(campaign_dir)
    if not root.is_dir():
        return {"ok": False, "error": f"Campaign dir not found: {campaign_dir}"}

    variants_dir = root / "variants"
    if not variants_dir.is_dir():
        return {"ok": False, "error": f"variants/ missing in {campaign_dir}"}

    variant_dirs = sorted(d for d in variants_dir.iterdir() if d.is_dir())
    if not variant_dirs:
        return {"ok": False, "error": "No variants to export"}

    headlines: list[str] = []
    bodies: list[str] = []
    ctas: list[str] = []
    image_manifest: list[dict] = []

    dco_dir = root / "dco_components"
    images_dir = dco_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    for vdir in variant_dirs:
        copy_path = vdir / "copy.json"
        if not copy_path.exists():
            continue
        try:
            copy = json.loads(copy_path.read_text())
        except json.JSONDecodeError:
            continue

        headlines.append(copy.get("headline", ""))
        bodies.append(copy.get("body", ""))
        ctas.append(copy.get("cta", ""))

        fmt_name = copy.get("format")
        if not fmt_name:
            continue
        try:
            fmt = get_format(fmt_name)
        except KeyError:
            continue

        if fmt.kind != "static":
            continue

        rendered = vdir / f"{fmt_name}.png"
        if not rendered.exists():
            continue

        aspect = _aspect_slug(fmt.aspect)
        out_name = f"img_{vdir.name}_{aspect}.png"
        out_path = images_dir / out_name
        shutil.copy2(rendered, out_path)
        image_manifest.append({
            "source_variant": vdir.name,
            "format": fmt_name,
            "aspect": fmt.aspect,
            "path": f"dco_components/images/{out_name}",
        })

    headlines = _dedup_preserving_order(headlines)
    bodies = _dedup_preserving_order(bodies)
    ctas = _dedup_preserving_order(ctas)

    (dco_dir / "headlines.json").write_text(json.dumps(headlines, indent=2))
    (dco_dir / "bodies.json").write_text(json.dumps(bodies, indent=2))
    (dco_dir / "ctas.json").write_text(json.dumps(ctas, indent=2))
    (dco_dir / "images.json").write_text(json.dumps(image_manifest, indent=2))

    return {
        "ok": True,
        "dco_dir": str(dco_dir.relative_to(root)),
        "headline_count": len(headlines),
        "body_count": len(bodies),
        "cta_count": len(ctas),
        "image_count": len(image_manifest),
    }


def register(mcp) -> None:
    @mcp.tool()
    def adclip_export_dco(campaign_dir: str) -> str:
        """Export a campaign's variants as Meta DCO modular components.

        Writes a ``dco_components/`` directory alongside ``variants/``:

        - headlines.json, bodies.json, ctas.json — deduplicated copy pools
        - images/img_{variant_id}_{aspect}.png — one per rendered static variant
        - images.json — index mapping source variant + format to exported image

        Args:
            campaign_dir: path to the campaign output directory.
        """
        return json.dumps(_export_dco_impl(campaign_dir))
