"""Campaign directory: on-disk layout, stable identity, and manifest."""

from __future__ import annotations

import hashlib
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


def _artifact_sha256(root: Path, relative_path: object) -> str | None:
    if not isinstance(relative_path, str) or not relative_path:
        return None
    root_resolved = root.resolve()
    artifact = (root / relative_path).resolve()
    if not artifact.is_relative_to(root_resolved):
        raise ValueError(f"Manifest artifact path escapes campaign directory: {relative_path!r}")
    if not artifact.is_file():
        return None
    digest = hashlib.sha256()
    with artifact.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_campaign_state(
    root: str | Path,
    *,
    preferred_campaign_id: str | None = None,
) -> dict[str, object]:
    """Return a stable campaign identity, creating it once if needed.

    ``preferred_campaign_id`` lets a portable manifest restore the identity when
    a copied directory is missing its hidden local state file.
    """

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

    campaign_id = preferred_campaign_id or f"cmp_{uuid.uuid4().hex}"
    if not campaign_id.startswith("cmp_"):
        raise ValueError("campaign_id must use the cmp_ prefix")
    state: dict[str, object] = {
        "schema_version": "campaign-state-v1",
        "campaign_id": campaign_id,
        "created_at": _utc_now(),
    }
    _atomic_write_json(path, state)
    return state


def creative_id_for(
    campaign_id: str,
    variant_id: str,
    format_name: str,
    *,
    artifact_sha256: str | None = None,
) -> str:
    """Return a deterministic ID for an exact creative artifact when possible."""

    material = artifact_sha256 or "unhashed-artifact"
    identity = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"adclip:{campaign_id}:creative:{variant_id}:{format_name}:{material}",
    )
    return f"crv_{identity.hex}"


def _entry_with_identity(campaign_id: str, entry: dict, root: Path) -> dict:
    output = dict(entry)
    variant_id = output.get("variant_id")
    format_name = output.get("format")
    if not isinstance(variant_id, str) or not isinstance(format_name, str):
        return output

    artifact_hash = _artifact_sha256(root, output.get("path"))
    if artifact_hash is not None:
        output["artifact_sha256"] = artifact_hash
        output["creative_id"] = creative_id_for(
            campaign_id,
            variant_id,
            format_name,
            artifact_sha256=artifact_hash,
        )
    elif not output.get("creative_id"):
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
    """Load a manifest and reconcile stable campaign/creative IDs and hashes."""

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

    manifest_campaign_id = manifest.get("campaign_id")
    preferred = (
        manifest_campaign_id
        if isinstance(manifest_campaign_id, str) and manifest_campaign_id.startswith("cmp_")
        else None
    )
    state = ensure_campaign_state(root, preferred_campaign_id=preferred)
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
    identified = [_entry_with_identity(campaign_id, entry, root) for entry in entries]
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
        "entries": [
            _entry_with_identity(campaign_id, entry, root)
            for entry in entries
        ],
    }
    if models:
        manifest["models"] = models
    path = root / "manifest.json"
    _atomic_write_json(path, manifest)
    return path
