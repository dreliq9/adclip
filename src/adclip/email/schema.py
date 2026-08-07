"""Domain models for email campaigns and editable email documents."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


EmailCampaignType = Literal["marketing", "transactional"]
EmailBlockKind = Literal[
    "heading",
    "paragraph",
    "image",
    "button",
    "divider",
    "spacer",
    "raw_html",
]
EmailPatchOperation = Literal[
    "replace_text",
    "set_link",
    "set_image",
    "replace_block_html",
    "remove_block",
]

_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class EmailBlock(BaseModel):
    """One editable block in an email message."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: EmailBlockKind
    text: str = ""
    href: str | None = None
    src: str | None = None
    alt: str = ""
    align: Literal["left", "center", "right"] = "left"
    background_color: str | None = None
    text_color: str | None = None
    font_size: int | None = Field(default=None, ge=10, le=72)
    padding: int = Field(default=20, ge=0, le=64)
    height: int | None = Field(default=None, ge=0, le=240)
    raw_html: str | None = None

    @model_validator(mode="after")
    def validate_block(self) -> "EmailBlock":
        if not _ID_RE.fullmatch(self.id):
            raise ValueError(
                "block id must start with a letter and contain only letters, "
                "numbers, underscores, or hyphens"
            )
        if self.background_color and not _HEX_RE.fullmatch(self.background_color):
            raise ValueError("background_color must be a six-digit hex color")
        if self.text_color and not _HEX_RE.fullmatch(self.text_color):
            raise ValueError("text_color must be a six-digit hex color")

        if self.kind in {"heading", "paragraph", "button"} and not self.text.strip():
            raise ValueError(f"{self.kind} block requires text")
        if self.kind == "button" and not self.href:
            raise ValueError("button block requires href")
        if self.kind == "image" and not self.src:
            raise ValueError("image block requires src")
        if self.kind == "raw_html" and not (self.raw_html or "").strip():
            raise ValueError("raw_html block requires raw_html")
        if self.kind == "spacer" and self.height is None:
            self.height = 24
        return self


class EmailMessage(BaseModel):
    """A single message in an email campaign or sequence."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    delay_days: int = Field(default=0, ge=0, le=365)
    subject: str = Field(min_length=1, max_length=160)
    preheader: str = Field(default="", max_length=240)
    blocks: list[EmailBlock] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_message(self) -> "EmailMessage":
        if not _ID_RE.fullmatch(self.id):
            raise ValueError(
                "message id must start with a letter and contain only letters, "
                "numbers, underscores, or hyphens"
            )
        ids = [block.id for block in self.blocks]
        if len(ids) != len(set(ids)):
            raise ValueError("email block ids must be unique within a message")
        return self


class EmailCampaignBrief(BaseModel):
    """Provider-neutral brief for a marketing or transactional email sequence."""

    model_config = ConfigDict(extra="forbid")

    name: str
    product: str
    value_prop: str
    audience: str
    objective: str
    tone: str = "clear, useful, and specific"
    offer: str | None = None
    cta: str = "Learn more"
    landing_page_url: str = "{{landing_page_url}}"

    sender_name: str
    sender_email: str
    reply_to: str | None = None
    campaign_type: EmailCampaignType = "marketing"
    list_name: str = "marketing"
    language: str = "en"
    direction: Literal["ltr", "rtl", "auto"] = "ltr"

    sequence_length: int = Field(default=1, ge=1, le=12)
    cadence_days: list[int] = Field(default_factory=list)

    logo_url: str | None = None
    brand_colors: list[str] = Field(default_factory=list)
    unsubscribe_url: str = "{{unsubscribe_url}}"
    physical_address: str = "{{physical_address}}"

    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    output_dir: str = "adclip_email_campaign"

    @model_validator(mode="after")
    def validate_brief(self) -> "EmailCampaignBrief":
        if not _EMAIL_RE.fullmatch(self.sender_email):
            raise ValueError("sender_email must be a valid email address")
        if self.reply_to and not _EMAIL_RE.fullmatch(self.reply_to):
            raise ValueError("reply_to must be a valid email address")
        if not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", self.language):
            raise ValueError("language must be a BCP-47-like language tag")
        if self.cadence_days:
            if len(self.cadence_days) != self.sequence_length:
                raise ValueError(
                    "cadence_days must be empty or contain one value per email"
                )
            if any(day < 0 for day in self.cadence_days):
                raise ValueError("cadence_days values must be non-negative")
            if self.cadence_days != sorted(self.cadence_days):
                raise ValueError("cadence_days must be non-decreasing")
        for color in self.brand_colors:
            if not _HEX_RE.fullmatch(color):
                raise ValueError(
                    f"brand color {color!r} must be a six-digit hex color"
                )
        return self

    def resolved_cadence(self) -> list[int]:
        if self.cadence_days:
            return list(self.cadence_days)
        if self.sequence_length == 1:
            return [0]
        return [index * 2 for index in range(self.sequence_length)]


class EmailHtmlPatch(BaseModel):
    """One safe, marker-targeted edit to rendered email HTML or message blocks."""

    model_config = ConfigDict(extra="forbid")

    block_id: str
    op: EmailPatchOperation
    find: str | None = None
    value: str | None = None
    href: str | None = None
    src: str | None = None
    alt: str | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> "EmailHtmlPatch":
        if not _ID_RE.fullmatch(self.block_id):
            raise ValueError("patch block_id has invalid characters")
        if self.op == "replace_text" and (
            self.find is None or self.value is None
        ):
            raise ValueError("replace_text requires find and value")
        if self.op == "set_link" and not self.href:
            raise ValueError("set_link requires href")
        if self.op == "set_image" and not self.src:
            raise ValueError("set_image requires src")
        if self.op == "replace_block_html" and self.value is None:
            raise ValueError("replace_block_html requires value")
        return self


class EmailLintContext(BaseModel):
    """Metadata used when linting imported or edited HTML."""

    model_config = ConfigDict(extra="forbid")

    campaign_type: EmailCampaignType = "marketing"
    subject: str = ""
    preheader: str = ""
    unsubscribe_url: str = "{{unsubscribe_url}}"
    physical_address: str = "{{physical_address}}"
    headers: dict[str, str] = Field(default_factory=dict)
