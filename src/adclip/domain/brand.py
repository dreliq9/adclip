"""BrandKit, product, and claim domain models."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class BrandVoice(BaseModel):
    tone: list[str] = Field(default_factory=list)
    preferred_terms: list[str] = Field(default_factory=list)
    prohibited_terms: list[str] = Field(default_factory=list)
    style_notes: str = ""


class BrandVisual(BaseModel):
    colors: list[str] = Field(default_factory=list)
    typography: list[str] = Field(default_factory=list)
    logo_artifact_uri: str | None = None
    visual_notes: str = ""


class BrandKit(BaseModel):
    id: str = Field(default_factory=lambda: _id("brd"))
    slug: str
    name: str
    description: str = ""
    website_url: str | None = None
    voice: BrandVoice = Field(default_factory=BrandVoice)
    visual: BrandVisual = Field(default_factory=BrandVisual)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def validate_slug(self) -> "BrandKit":
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", self.slug):
            raise ValueError("brand slug must use lowercase letters, numbers, and hyphens")
        return self


class ProductProfile(BaseModel):
    id: str = Field(default_factory=lambda: _id("prd"))
    brand_id: str
    name: str
    description: str = ""
    value_prop: str = ""
    audiences: list[str] = Field(default_factory=list)
    offers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


ClaimStatus = Literal["unreviewed", "approved", "restricted", "rejected"]


class ClaimRecord(BaseModel):
    id: str = Field(default_factory=lambda: _id("clm"))
    brand_id: str
    product_id: str | None = None
    text: str
    status: ClaimStatus = "unreviewed"
    evidence_source_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
