"""Platform-neutral deployment and performance observation schemas."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PerformanceMetrics(BaseModel):
    """Metrics normalized enough for cross-platform creative comparison.

    Platform-specific action names are intentionally preserved in ``actions``
    and ``action_values`` rather than being guessed into a universal conversion
    taxonomy too early.
    """

    impressions: int = Field(default=0, ge=0)
    reach: int | None = Field(default=None, ge=0)
    clicks: int = Field(default=0, ge=0)
    outbound_clicks: float = Field(default=0.0, ge=0)
    spend: float = Field(default=0.0, ge=0)
    actions: dict[str, float] = Field(default_factory=dict)
    action_values: dict[str, float] = Field(default_factory=dict)
    video: dict[str, float] = Field(default_factory=dict)

    @field_validator("actions", "action_values", "video")
    @classmethod
    def _non_negative_maps(cls, value: dict[str, float]) -> dict[str, float]:
        if any(number < 0 for number in value.values()):
            raise ValueError("performance metric maps cannot contain negative values")
        return value


class DeploymentRecord(BaseModel):
    """Join one adclip creative to one external platform deployment."""

    id: str = Field(min_length=1)
    campaign_id: str = Field(min_length=1)
    creative_id: str = Field(min_length=1)
    variant_id: str = Field(min_length=1)
    format: str | None = None
    platform: str = Field(min_length=1, pattern=r"^[a-z0-9_-]+$")
    account_id: str = Field(min_length=1)
    external_ad_id: str = Field(min_length=1)
    external_campaign_id: str | None = None
    external_adset_id: str | None = None
    external_creative_id: str | None = None
    external_name: str | None = None
    status: str | None = None
    linked_at: datetime = Field(default_factory=utc_now)
    last_synced_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PerformanceObservation(BaseModel):
    """Immutable-in-meaning measurement for one deployment and date window."""

    id: str = Field(min_length=1)
    deployment_id: str = Field(min_length=1)
    campaign_id: str = Field(min_length=1)
    creative_id: str = Field(min_length=1)
    variant_id: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    external_ad_id: str = Field(min_length=1)
    period_start: date
    period_end: date
    currency: str | None = None
    action_report_time: str = "conversion"
    metrics: PerformanceMetrics = Field(default_factory=PerformanceMetrics)
    source_api_version: str | None = None
    fetched_at: datetime = Field(default_factory=utc_now)
    raw: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _window_order(self) -> PerformanceObservation:
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self
