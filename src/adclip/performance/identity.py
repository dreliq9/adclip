"""Deterministic IDs for deployments and measurement windows."""

from __future__ import annotations

import json
import uuid
from datetime import date


def _stable(prefix: str, value: str) -> str:
    identity = uuid.uuid5(uuid.NAMESPACE_URL, value)
    return f"{prefix}_{identity.hex}"


def deployment_id_for(platform: str, account_id: str, external_ad_id: str) -> str:
    return _stable(
        "dep",
        f"adclip:deployment:{platform}:{account_id}:{external_ad_id}",
    )


def observation_id_for(
    deployment_id: str,
    period_start: date,
    period_end: date,
    *,
    action_report_time: str,
    dimensions: dict[str, str] | None = None,
) -> str:
    dimension_key = json.dumps(dimensions or {}, sort_keys=True, separators=(",", ":"))
    return _stable(
        "obs",
        (
            f"adclip:observation:{deployment_id}:{period_start.isoformat()}:"
            f"{period_end.isoformat()}:{action_report_time}:{dimension_key}"
        ),
    )
