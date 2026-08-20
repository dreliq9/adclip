"""SourceLibrary domain models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


SourceKind = Literal[
    "file",
    "website",
    "landing_page",
    "product_page",
    "review",
    "testimonial",
    "research",
    "policy",
    "reference",
    "other",
]

RightsStatus = Literal[
    "unknown",
    "owned",
    "licensed",
    "public_domain",
    "permission_granted",
    "reference_only",
]


class SourceRecord(BaseModel):
    id: str = Field(default_factory=lambda: _id("src"))
    brand_id: str
    product_id: str | None = None
    kind: SourceKind = "other"
    title: str
    uri: str
    rights: RightsStatus = "unknown"
    sha256: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
