"""Compose step: given copy + raw visual, build a render plan.

For static formats: emit overlay descriptors (headline, CTA, optional logo).
For text-only formats (google_rsa): no overlays — copy is the ad.
For video formats: covered in Phase 6.
"""

from __future__ import annotations

from adclip.formats import get_format


def build_overlay_plan(
    *,
    format_name: str,
    copy: dict,
    logo_path: str | None,
) -> dict:
    fmt = get_format(format_name)

    if fmt.kind == "text":
        return {
            "format": format_name,
            "kind": "text",
            "overlays": [],
            "copy": copy,
        }

    if fmt.kind == "static":
        overlays: list[dict] = [
            {
                "type": "text",
                "role": "headline",
                "text": copy["headline"],
                "position": "top",
                "pad": 48,
                "font_size": max(40, fmt.width // 20),
                "color": "#ffffff",
                "stroke": "#000000",
            },
            {
                "type": "text",
                "role": "cta",
                "text": copy["cta"],
                "position": "bottom",
                "pad": 48,
                "font_size": max(36, fmt.width // 24),
                "color": "#ffffff",
                "stroke": "#000000",
            },
        ]
        if logo_path:
            overlays.append({
                "type": "image",
                "role": "logo",
                "path": logo_path,
                "position": "bottom_right",
                "pad": 32,
                "max_width": fmt.width // 8,
            })
        return {
            "format": format_name,
            "kind": "static",
            "overlays": overlays,
            "copy": copy,
        }

    # video: handled in Phase 6
    return {
        "format": format_name,
        "kind": "video",
        "overlays": [],
        "copy": copy,
        "note": "video compose in Phase 6",
    }
