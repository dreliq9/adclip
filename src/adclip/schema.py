"""AdBrief — the API boundary for adclip."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from adclip.formats import FORMATS


VariantStrategy = Literal["angles", "hooks", "visuals", "modular_components"]
PolicyProfile = Literal["default", "crypto", "health", "alcohol", "financial_services"]


class AdBrief(BaseModel):
    # Product / service
    product: str = Field(min_length=1)
    value_prop: str = Field(min_length=1)
    audience: str = Field(min_length=1)

    # Creative direction
    angles: list[str] = Field(min_length=1)
    tone: str = Field(min_length=1)
    cta: str = Field(min_length=1)

    # Format and variant strategy
    formats: list[str] = Field(min_length=1)
    variants: int = Field(default=5, ge=1, le=50)
    pool_size: int = Field(default=15, ge=1, le=100)
    variant_strategy: VariantStrategy = "angles"

    # Brand assets
    logo_path: str | None = None
    brand_colors: list[str] = []
    product_screenshots: list[str] = []
    font_family: str | None = None

    # Constraints
    must_include: list[str] = []
    must_avoid: list[str] = []
    policy_profile: PolicyProfile = "default"

    # Output
    output_dir: str = Field(min_length=1)
    budget_usd: float | None = Field(default=None, gt=0)

    @field_validator("formats")
    @classmethod
    def _formats_must_be_known(cls, v: list[str]) -> list[str]:
        unknown = [f for f in v if f not in FORMATS]
        if unknown:
            raise ValueError(f"Unknown formats: {unknown}. Known: {sorted(FORMATS)}")
        return v

    @model_validator(mode="after")
    def _pool_size_ge_variants(self) -> AdBrief:
        if self.pool_size < self.variants:
            raise ValueError(
                f"pool_size ({self.pool_size}) must be >= variants ({self.variants})"
            )
        return self
