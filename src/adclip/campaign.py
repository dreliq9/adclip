"""Campaign directory: on-disk layout, stable identity, and manifest."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from adclip.schema import AdBrief


CAMPAIGN_STATE_FILENAME = ".adclip_campaign.json"
MANIFEST_SCHEMA_VERSION = "creative-manifest-v2"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def ensure_campaign_state(root: str | Path) -> dict[str, object]:
    """Return a stable local campaign identity, creating it once if needed."""

    directory = Path(root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / CAMPAIGN_STATE_FILENAME
    if path.exists():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} is not valid JSON: {exc}") from exc
        if not isinstance(value, dict) or not isinstance(value.get("campaign_id"), str):
            raise ValueError(f"{path} does not contain a valid campaign_id")
        return value

    state: dict[str, object] = {
        "schema_version": "campaign-state-v1",
        "campaign_id": f"cmp_{uuid.uuid4().hex}",
        "created_at": _utc_now(),
    }
    _atomic_write_json(path, state)
    return state


def creative_id_for(campaign_id: str, variant_id: str, format_name: str) -> str:
    """Return a deterministic creative ID for one campaign variant artifact."""

    identity = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"adclip:{campaign_id}:creative:{variant_id}:{format_name}",
    )
    return f"crv_{identity.hex}"


def _entry_with_identity(campaign_id: str, entry: dict) -> dict:
    output = dict(entry)
    variant_id = output.get("variant_id")
    format_name = output.get("format")
    if (
        not output.get("creative_id")
        and isinstance(variant_id, str)
        and isinstance(format_name, str)
    ):
        output["creative_id"] = creative_id_for(
            campaign_id,
            variant_id,
            format_name,
        )
    return output


def init_campaign_dir(brief: AdBrief) -> Path:
    root = Path(brief.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    ensure_campaign_state(root)
    (root / "variants").mkdir(exist_ok=True)
    (root / "pool_rejected").mkdir(exist_ok=True)
    (root / "brief.json").write_text(
        json.dumps(brief.model_dump(), indent=2),
        encoding="utf-8",
    )
    return root


def variant_dir(brief: AdBrief, variant_id: str) -> Path:
    directory = Path(brief.output_dir) / "variants" / variant_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def ensure_manifest_identity(campaign_dir: str | Path) -> dict:
    """Load a manifest and backfill stable campaign/creative IDs if absent."""

    root = Path(campaign_dir)
    path = root / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"manifest.json missing in {root}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest.json unreadable: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("manifest.json must contain an object")

    state = ensure_campaign_state(root)
    campaign_id = str(state["campaign_id"])
    changed = False
    if manifest.get("campaign_id") != campaign_id:
        manifest["campaign_id"] = campaign_id
        changed = True
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        manifest["schema_version"] = MANIFEST_SCHEMA_VERSION
        changed = True

    entries = manifest.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError("manifest entries must be a list")
    identified = [_entry_with_identity(campaign_id, entry) for entry in entries]
    if identified != entries:
        manifest["entries"] = identified
        changed = True

    if changed:
        _atomic_write_json(path, manifest)
    return manifest


def write_manifest(
    brief: AdBrief,
    *,
    entries: list[dict],
    cost_usd: float,
    models: dict[str, object] | None = None,
) -> Path:
    root = Path(brief.output_dir)
    state = ensure_campaign_state(root)
    campaign_id = str(state["campaign_id"])
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "generated_at": _utc_now(),
        "brief_summary": {
            "product": brief.product,
            "formats": brief.formats,
            "angles": brief.angles,
            "variants": brief.variants,
            "pool_size": brief.pool_size,
        },
        "total_cost_usd": cost_usd,
        "entries": [_entry_with_identity(campaign_id, entry) for entry in entries],
    }
    if models:
        manifest["models"] = models
    path = root / "manifest.json"
    _atomic_write_json(path, manifest)
    return path
