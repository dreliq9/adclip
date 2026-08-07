"""Portable file-backed performance store used before SQLite becomes authoritative."""

from __future__ import annotations

import json
from pathlib import Path

from adclip.campaign import ensure_manifest_identity
from adclip.performance.schema import DeploymentRecord, PerformanceObservation


PERFORMANCE_SCHEMA_VERSION = "performance-v1"


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def performance_dir(campaign_dir: str | Path) -> Path:
    directory = Path(campaign_dir) / "performance"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _read_collection(path: Path, key: str) -> list[dict]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict) or not isinstance(value.get(key, []), list):
        raise ValueError(f"{path} must contain a {key!r} array")
    return value.get(key, [])


def campaign_manifest(campaign_dir: str | Path) -> dict:
    return ensure_manifest_identity(campaign_dir)


def find_creative_entry(
    campaign_dir: str | Path,
    *,
    variant_id: str | None = None,
    creative_id: str | None = None,
) -> dict:
    if bool(variant_id) == bool(creative_id):
        raise ValueError("Pass exactly one of variant_id or creative_id")
    manifest = campaign_manifest(campaign_dir)
    entries = manifest.get("entries", [])
    key = "variant_id" if variant_id is not None else "creative_id"
    wanted = variant_id if variant_id is not None else creative_id
    matches = [entry for entry in entries if entry.get(key) == wanted]
    if not matches:
        raise ValueError(f"Creative not found for {key}={wanted!r}")
    if len(matches) > 1:
        raise ValueError(f"Multiple creative entries found for {key}={wanted!r}")
    return dict(matches[0])


def load_deployments(campaign_dir: str | Path) -> list[DeploymentRecord]:
    path = performance_dir(campaign_dir) / "deployments.json"
    return [
        DeploymentRecord.model_validate(value)
        for value in _read_collection(path, "deployments")
    ]


def write_deployments(
    campaign_dir: str | Path,
    deployments: list[DeploymentRecord],
) -> Path:
    manifest = campaign_manifest(campaign_dir)
    path = performance_dir(campaign_dir) / "deployments.json"
    payload = {
        "schema_version": PERFORMANCE_SCHEMA_VERSION,
        "campaign_id": manifest["campaign_id"],
        "deployments": [
            deployment.model_dump(mode="json")
            for deployment in sorted(deployments, key=lambda item: item.id)
        ],
    }
    _atomic_write_json(path, payload)
    return path


def upsert_deployment(
    campaign_dir: str | Path,
    deployment: DeploymentRecord,
) -> DeploymentRecord:
    deployments = load_deployments(campaign_dir)
    by_id = {item.id: item for item in deployments}
    by_id[deployment.id] = deployment
    write_deployments(campaign_dir, list(by_id.values()))
    return deployment


def load_observations(campaign_dir: str | Path) -> list[PerformanceObservation]:
    path = performance_dir(campaign_dir) / "observations.json"
    return [
        PerformanceObservation.model_validate(value)
        for value in _read_collection(path, "observations")
    ]


def write_observations(
    campaign_dir: str | Path,
    observations: list[PerformanceObservation],
) -> Path:
    manifest = campaign_manifest(campaign_dir)
    path = performance_dir(campaign_dir) / "observations.json"
    payload = {
        "schema_version": PERFORMANCE_SCHEMA_VERSION,
        "campaign_id": manifest["campaign_id"],
        "observations": [
            observation.model_dump(mode="json")
            for observation in sorted(observations, key=lambda item: item.id)
        ],
    }
    _atomic_write_json(path, payload)
    return path


def upsert_observations(
    campaign_dir: str | Path,
    observations: list[PerformanceObservation],
) -> list[PerformanceObservation]:
    existing = load_observations(campaign_dir)
    by_id = {item.id: item for item in existing}
    for observation in observations:
        by_id[observation.id] = observation
    merged = list(by_id.values())
    write_observations(campaign_dir, merged)
    return merged
