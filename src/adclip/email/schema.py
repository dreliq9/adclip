"""Email campaign domain models for adclip's standalone email workflow."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


EmailMessageType = Literal["marketing", "transactional"]
EmailTemplate = Literal["promotion", "announcement", "newsletter", "nurture"]
EmailBlockKind = Literal[
    "logo",
    "eyebrow",
    "heading",
    "paragraph",
    "image",
    "button",
    "divider",
    "spacer",
]
EmailAlignment = Literal["left", "center", "right"]
EmailIssueSeverity = Literal["error", "warning", "info"]

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_BLOCK_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_TEMPLATE_TOKEN_RE = re.compile(r"^\{\{[A-Za-z0-9_.-]+\}\}$")


def _is_url_or_token(value: str) -> bool:
    return (
        value.startswith(("https://", "http://", "mailto:", "tel:"))
        or bool(_TEMPLATE_TOKEN_RE.fullmatch(value))
    )


class EmailSender(BaseModel):
    """Visible sender identity and compliance address."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    email: str = Field(min_length=3, max_length=320)
    reply_to: str | None = Field(default=None, max_length=320)
    physical_address: str = Field(min_length=1, max_length=500)

    @field_validator("email", "reply_to")
    @classmethod
    def _basic_email_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("must be an email address")
        return value


class EmailTheme(BaseModel):
    """Small design-token set used by the native HTML renderer."""

    model_config = ConfigDict(extra="forbid")

    content_width: int = Field(default=600, ge=320, le=720)
    background_color: str = "#F3F4F6"
    content_background_color: str = "#FFFFFF"
    text_color: str = "#111827"
    muted_text_color: str = "#6B7280"
    accent_color: str = "#2563EB"
    button_text_color: str = "#FFFFFF"
    font_family: str = Field(
        default="Arial, Helvetica, sans-serif",
        min_length=1,
        max_length=160,
    )
    border_radius: int = Field(default=8, ge=0, le=40)

    @field_validator(
        "background_color",
        "content_background_color",
        "text_color",
        "muted_text_color",
        "accent_color",
        "button_text_color",
    )
    @classmethod
    def _hex_color(cls, value: str) -> str:
        if not _COLOR_RE.fullmatch(value):
            raise ValueError("must be a six-digit hex color such as #2563EB")
        return value.upper()


class EmailTracking(BaseModel):
    """UTM settings applied to eligible campaign links."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    source: str = "email"
    medium: str = "email"
    campaign: str | None = None
    content: str | None = None


class EmailBlock(BaseModel):
    """Editable, stable-ID block in the canonical email document."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: EmailBlockKind
    text: str | None = None
    href: str | None = None
    src: str | None = None
    alt: str | None = None
    align: EmailAlignment = "left"
    padding_top: int = Field(default=8, ge=0, le=80)
    padding_right: int = Field(default=32, ge=0, le=80)
    padding_bottom: int = Field(default=8, ge=0, le=80)
    padding_left: int = Field(default=32, ge=0, le=80)
    font_size: int | None = Field(default=None, ge=10, le=72)
    width: int | None = Field(default=None, ge=1, le=1200)
    height: int | None = Field(default=None, ge=1, le=1200)
    spacer_height: int | None = Field(default=None, ge=1, le=160)

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if not _BLOCK_ID_RE.fullmatch(value):
            raise ValueError(
                "block id must start with a letter and contain only letters, "
                "numbers, underscores, or hyphens"
            )
        return value

    @field_validator("href", "src")
    @classmethod
    def _url_or_token(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _is_url_or_token(value):
            raise ValueError("must be an absolute URL, mailto/tel link, or template token")
        return value

    @model_validator(mode="after")
    def _kind_requirements(self) -> EmailBlock:
        text_kinds = {"eyebrow", "heading", "paragraph", "button"}
        if self.kind in text_kinds and not (self.text or "").strip():
            raise ValueError(f"{self.kind} block requires text")
        if self.kind == "button" and not self.href:
            raise ValueError("button block requires href")
        if self.kind in {"image", "logo"}:
            if not self.src:
                raise ValueError(f"{self.kind} block requires src")
            if not (self.alt or "").strip():
                raise ValueError(f"{self.kind} block requires non-empty alt text")
        if self.kind == "spacer" and self.spacer_height is None:
            self.spacer_height = 24
        return self


class EmailContent(BaseModel):
    """Model-generated or manually supplied campaign copy."""

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=200)
    preview_text: str = Field(min_length=1, max_length=300)
    eyebrow: str | None = Field(default=None, max_length=120)
    headline: str = Field(min_length=1, max_length=240)
    paragraphs: list[str] = Field(min_length=1, max_length=8)
    cta_label: str = Field(min_length=1, max_length=80)
    footer_note: str | None = Field(default=None, max_length=500)


class EmailCampaignBrief(BaseModel):
    """Input contract for a model-assisted or deterministic email campaign."""

    model_config = ConfigDict(extra="forbid")

    campaign_name: str = Field(min_length=1, max_length=160)
    product: str = Field(min_length=1, max_length=240)
    value_prop: str = Field(min_length=1, max_length=1000)
    audience: str = Field(min_length=1, max_length=1000)
    objective: str = Field(min_length=1, max_length=1000)
    tone: str = Field(min_length=1, max_length=300)
    cta: str = Field(min_length=1, max_length=120)
    landing_url: str
    sender: EmailSender
    output_dir: str = Field(min_length=1)

    offer: str | None = Field(default=None, max_length=1000)
    template: EmailTemplate = "promotion"
    message_type: EmailMessageType = "marketing"
    locale: str = Field(default="en-US", min_length=2, max_length=35)
    variants: int = Field(default=1, ge=1, le=10)
    logo_url: str | None = None
    unsubscribe_url: str = "{{unsubscribe_url}}"
    preferences_url: str | None = None
    theme: EmailTheme = Field(default_factory=EmailTheme)
    tracking: EmailTracking = Field(default_factory=EmailTracking)

    subject: str | None = Field(default=None, max_length=200)
    preview_text: str | None = Field(default=None, max_length=300)
    eyebrow: str | None = Field(default=None, max_length=120)
    headline: str | None = Field(default=None, max_length=240)
    body_paragraphs: list[str] = Field(default_factory=list, max_length=8)
    footer_note: str | None = Field(default=None, max_length=500)

    @field_validator("landing_url", "logo_url", "unsubscribe_url", "preferences_url")
    @classmethod
    def _brief_urls(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _is_url_or_token(value):
            raise ValueError("must be an absolute URL or template token")
        return value


class EmailCampaignDocument(BaseModel):
    """Canonical editable email document used to render HTML, text, and MIME."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["email-campaign/v1"] = "email-campaign/v1"
    campaign_name: str = Field(min_length=1, max_length=160)
    variant_id: str = Field(pattern=r"^v[0-9]{2}$")
    message_type: EmailMessageType = "marketing"
    locale: str = Field(default="en-US", min_length=2, max_length=35)
    sender: EmailSender
    subject: str = Field(min_length=1, max_length=200)
    preview_text: str = Field(min_length=1, max_length=300)
    unsubscribe_url: str
    preferences_url: str | None = None
    theme: EmailTheme = Field(default_factory=EmailTheme)
    tracking: EmailTracking = Field(default_factory=EmailTracking)
    blocks: list[EmailBlock] = Field(min_length=1, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("unsubscribe_url", "preferences_url")
    @classmethod
    def _document_urls(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _is_url_or_token(value):
            raise ValueError("must be an absolute URL or template token")
        return value

    @model_validator(mode="after")
    def _unique_block_ids(self) -> EmailCampaignDocument:
        ids = [block.id for block in self.blocks]
        duplicates = sorted({block_id for block_id in ids if ids.count(block_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate block ids: {duplicates}")
        return self


class EmailBlockInsertion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block: EmailBlock
    after_id: str | None = None


class EmailCampaignPatch(BaseModel):
    """Safe structured edit contract for an existing campaign variant."""

    model_config = ConfigDict(extra="forbid")

    subject: str | None = Field(default=None, min_length=1, max_length=200)
    preview_text: str | None = Field(default=None, min_length=1, max_length=300)
    sender: dict[str, Any] = Field(default_factory=dict)
    theme: dict[str, Any] = Field(default_factory=dict)
    tracking: dict[str, Any] = Field(default_factory=dict)
    block_updates: dict[str, dict[str, Any]] = Field(default_factory=dict)
    insert_blocks: list[EmailBlockInsertion] = Field(default_factory=list)
    delete_blocks: list[str] = Field(default_factory=list)
    order: list[str] | None = None


class EmailValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: EmailIssueSeverity
    code: str
    message: str
    location: str | None = None


class EmailValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    issues: list[EmailValidationIssue] = Field(default_factory=list)
    metrics: dict[str, int | float | str | bool] = Field(default_factory=dict)

    @classmethod
    def from_issues(
        cls,
        issues: list[EmailValidationIssue],
        *,
        metrics: dict[str, int | float | str | bool] | None = None,
    ) -> EmailValidationReport:
        return cls(
            ok=not any(issue.severity == "error" for issue in issues),
            issues=issues,
            metrics=metrics or {},
        )


class EmailDeliveryPlan(BaseModel):
    """Provider-neutral handoff metadata; it does not authorize a send."""

    model_config = ConfigDict(extra="forbid")

    audience_segment: str | None = None
    scheduled_for: datetime | None = None
    provider: str | None = None
    tags: list[str] = Field(default_factory=list)
    idempotency_key: str | None = None
