"""Campaign directory: on-disk layout + manifest."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from adclip.schema import AdBrief


def init_campaign_dir(brief: AdBrief) -> Path:
    root = Path(brief.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "variants").mkdir(exist_ok=True)
    (root / "pool_rejected").mkdir(exist_ok=True)
    (root / "brief.json").write_text(json.dumps(brief.model_dump(), indent=2))
    return root


def variant_dir(brief: AdBrief, variant_id: str) -> Path:
    d = Path(brief.output_dir) / "variants" / variant_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_manifest(
    brief: AdBrief,
    *,
    entries: list[dict],
    cost_usd: float,
    models: dict[str, object] | None = None,
) -> Path:
    root = Path(brief.output_dir)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "brief_summary": {
            "product": brief.product,
            "formats": brief.formats,
            "angles": brief.angles,
            "variants": brief.variants,
            "pool_size": brief.pool_size,
        },
        "total_cost_usd": cost_usd,
        "entries": entries,
    }
    if models:
        manifest["models"] = models
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2))
    return path
