"""Provider-neutral email copy generation and document assembly."""

from __future__ import annotations

import json
import re
from typing import Protocol

from adclip.email.schema import (
    EmailBlock,
    EmailCampaignBrief,
    EmailCampaignDocument,
    EmailContent,
)


class EmailTextProvider(Protocol):
    async def generate(self, prompt: str, n: int) -> str: ...


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


_EMAIL_PROMPT = """\
You are a senior lifecycle and email marketing copywriter.
Create {variants} distinct email campaign variant(s) from the brief below.

Campaign: {campaign_name}
Product: {product}
Value proposition: {value_prop}
Audience: {audience}
Objective: {objective}
Offer: {offer}
Tone: {tone}
CTA direction: {cta}
Landing page: {landing_url}
Template: {template}
Locale: {locale}

Requirements:
- Keep subject lines honest and specific; do not imitate a reply or use deceptive urgency.
- Preview text must complement rather than repeat the subject.
- Use concise, skimmable paragraphs suitable for email.
- Do not invent testimonials, discounts, statistics, guarantees, or regulatory claims.
- CTA labels should be explicit and action-oriented.
- Return JSON only, with exactly this shape:

{{
  "variants": [
    {{
      "subject": "...",
      "preview_text": "...",
      "eyebrow": "... or null",
      "headline": "...",
      "paragraphs": ["...", "..."],
      "cta_label": "...",
      "footer_note": "... or null"
    }}
  ]
}}
"""


def build_email_prompt(brief: EmailCampaignBrief) -> str:
    return _EMAIL_PROMPT.format(
        variants=brief.variants,
        campaign_name=brief.campaign_name,
        product=brief.product,
        value_prop=brief.value_prop,
        audience=brief.audience,
        objective=brief.objective,
        offer=brief.offer or "(none)",
        tone=brief.tone,
        cta=brief.cta,
        landing_url=brief.landing_url,
        template=brief.template,
        locale=brief.locale,
    )


def parse_email_content_variants(raw: str) -> list[EmailContent]:
    match = _JSON_RE.search(raw)
    if not match:
        raise ValueError(f"No JSON object found in email response: {raw[:240]}")
    payload = json.loads(match.group(0))
    variants = payload.get("variants")
    if not isinstance(variants, list) or not variants:
        raise ValueError("Email response must contain a non-empty variants array")
    return [EmailContent.model_validate(item) for item in variants]


def _truncate(value: str, limit: int) -> str:
    clean = " ".join(value.split())
    if len(clean) <= limit:
        return clean
    return clean[: max(1, limit - 1)].rstrip() + "…"


def scaffold_email_content(brief: EmailCampaignBrief) -> EmailContent:
    """Build useful deterministic copy without invoking a model."""

    subject = brief.subject or f"{brief.product}: {brief.value_prop}"
    preview = brief.preview_text or brief.offer or brief.value_prop
    headline = brief.headline or brief.value_prop
    paragraphs = list(brief.body_paragraphs)
    if not paragraphs:
        paragraphs.append(brief.objective)
        if brief.offer:
            paragraphs.append(brief.offer)
        else:
            paragraphs.append(
                f"Built for {brief.audience.rstrip('.')} with a {brief.tone} approach."
            )
    return EmailContent(
        subject=_truncate(subject, 200),
        preview_text=_truncate(preview, 300),
        eyebrow=brief.eyebrow,
        headline=_truncate(headline, 240),
        paragraphs=[_truncate(paragraph, 1200) for paragraph in paragraphs],
        cta_label=_truncate(brief.cta, 80),
        footer_note=brief.footer_note,
    )


def document_from_content(
    brief: EmailCampaignBrief,
    content: EmailContent,
    *,
    variant_id: str,
    provenance: dict[str, object] | None = None,
) -> EmailCampaignDocument:
    blocks: list[EmailBlock] = []
    if brief.logo_url:
        blocks.append(
            EmailBlock(
                id="brand-logo",
                kind="logo",
                src=brief.logo_url,
                alt=f"{brief.product} logo",
                align="center",
                width=160,
                padding_top=28,
                padding_bottom=12,
            )
        )
    if content.eyebrow:
        blocks.append(
            EmailBlock(
                id="eyebrow",
                kind="eyebrow",
                text=content.eyebrow,
                align="center" if brief.template in {"promotion", "announcement"} else "left",
                padding_top=24,
                padding_bottom=4,
            )
        )
    blocks.append(
        EmailBlock(
            id="headline",
            kind="heading",
            text=content.headline,
            align="center" if brief.template in {"promotion", "announcement"} else "left",
            padding_top=12,
            padding_bottom=12,
        )
    )
    for index, paragraph in enumerate(content.paragraphs, start=1):
        blocks.append(
            EmailBlock(
                id=f"body-{index}",
                kind="paragraph",
                text=paragraph,
                align="left",
                padding_top=8,
                padding_bottom=8,
            )
        )
    blocks.append(
        EmailBlock(
            id="primary-cta",
            kind="button",
            text=content.cta_label,
            href=brief.landing_url,
            align="center",
            padding_top=20,
            padding_bottom=24,
        )
    )
    if content.footer_note:
        blocks.extend(
            [
                EmailBlock(id="content-divider", kind="divider"),
                EmailBlock(
                    id="footer-note",
                    kind="paragraph",
                    text=content.footer_note,
                    align="center",
                    font_size=13,
                    padding_top=12,
                    padding_bottom=12,
                ),
            ]
        )

    tracking = brief.tracking.model_copy(deep=True)
    if not tracking.campaign:
        tracking.campaign = brief.campaign_name
    metadata: dict[str, object] = {
        "template": brief.template,
        "product": brief.product,
        "audience": brief.audience,
        "objective": brief.objective,
    }
    if provenance:
        metadata["generation"] = provenance

    return EmailCampaignDocument(
        campaign_name=brief.campaign_name,
        variant_id=variant_id,
        message_type=brief.message_type,
        locale=brief.locale,
        sender=brief.sender,
        subject=content.subject,
        preview_text=content.preview_text,
        unsubscribe_url=brief.unsubscribe_url,
        preferences_url=brief.preferences_url,
        theme=brief.theme,
        tracking=tracking,
        blocks=blocks,
        metadata=metadata,
    )


def scaffold_email_documents(brief: EmailCampaignBrief) -> list[EmailCampaignDocument]:
    content = scaffold_email_content(brief)
    return [
        document_from_content(
            brief,
            content,
            variant_id=f"v{index:02d}",
            provenance={"mode": "deterministic-scaffold"},
        )
        for index in range(1, brief.variants + 1)
    ]


async def generate_email_documents(
    brief: EmailCampaignBrief,
    *,
    provider: EmailTextProvider,
    provider_name: str,
    model_name: str | None,
) -> list[EmailCampaignDocument]:
    raw = await provider.generate(build_email_prompt(brief), n=brief.variants)
    contents = parse_email_content_variants(raw)
    if len(contents) < brief.variants:
        raise ValueError(
            f"Email provider returned {len(contents)} variants; {brief.variants} requested"
        )
    provenance = {
        "mode": "model-generated",
        "provider": provider_name,
        "model": model_name,
    }
    return [
        document_from_content(
            brief,
            content,
            variant_id=f"v{index:02d}",
            provenance=provenance,
        )
        for index, content in enumerate(contents[: brief.variants], start=1)
    ]
