"""Provider-neutral campaign copy generation for email sequences."""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

from pydantic import ValidationError

from adclip.email.schema import (
    EmailCampaignBrief,
    EmailMessage,
)
from adclip.providers.contracts import TextGenerationProvider


_PROMPT = """\
You are a senior lifecycle and performance email strategist.

Create a coherent email campaign from the brief below.

Campaign: {name}
Campaign type: {campaign_type}
Product: {product}
Value proposition: {value_prop}
Audience: {audience}
Objective: {objective}
Offer: {offer}
Tone: {tone}
CTA direction: {cta}
CTA URL: {landing_page_url}
Sequence length: {sequence_length}
Cadence days: {cadence_days}
Must include: {must_include}
Must avoid: {must_avoid}

Requirements:
- Each message must have a distinct strategic role.
- Subjects should normally be 60 characters or fewer.
- Preheaders should normally be 120 characters or fewer.
- Use concrete, useful language rather than hype.
- Do not invent testimonials, statistics, certifications, scarcity, or guarantees.
- Marketing messages must end with a useful CTA, but the renderer owns the
  compliance footer and unsubscribe treatment.
- Use only these block kinds: heading, paragraph, image, button, divider, spacer.
- Image blocks require src and alt. Use the literal placeholder
  "{{{{hero_image_url}}}}" when a relevant image is useful.
- Button blocks require href and should normally use the campaign CTA URL.
- Block IDs must be unique within each message and contain only letters,
  numbers, underscores, or hyphens.
- Return exactly {sequence_length} messages in the requested cadence order.

Return JSON only, no markdown or prose, in this shape:
{{
  "emails": [
    {{
      "id": "email_01",
      "name": "Strategic role",
      "delay_days": 0,
      "subject": "...",
      "preheader": "...",
      "blocks": [
        {{"id": "headline", "kind": "heading", "text": "...", "align": "left"}},
        {{"id": "body_1", "kind": "paragraph", "text": "..."}},
        {{
          "id": "cta",
          "kind": "button",
          "text": "...",
          "href": "{landing_page_url}",
          "align": "left"
        }}
      ],
      "tags": ["awareness"]
    }}
  ]
}}
"""


def build_email_campaign_prompt(brief: EmailCampaignBrief) -> str:
    return _PROMPT.format(
        name=brief.name,
        campaign_type=brief.campaign_type,
        product=brief.product,
        value_prop=brief.value_prop,
        audience=brief.audience,
        objective=brief.objective,
        offer=brief.offer or "(none)",
        tone=brief.tone,
        cta=brief.cta,
        landing_page_url=brief.landing_page_url,
        sequence_length=brief.sequence_length,
        cadence_days=", ".join(str(day) for day in brief.resolved_cadence()),
        must_include=", ".join(brief.must_include) or "(none)",
        must_avoid=", ".join(brief.must_avoid) or "(none)",
    )


def _extract_json_object(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(raw[index:])
        except JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError(f"No JSON object found in email response: {raw[:200]}")


def parse_email_campaign_response(
    raw: str,
    brief: EmailCampaignBrief,
) -> list[EmailMessage]:
    payload = _extract_json_object(raw)
    values = payload.get("emails")
    if not isinstance(values, list):
        raise ValueError("email response must contain an emails array")
    if len(values) != brief.sequence_length:
        raise ValueError(
            f"expected {brief.sequence_length} emails, received {len(values)}"
        )

    messages: list[EmailMessage] = []
    cadence = brief.resolved_cadence()
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            raise ValueError(f"emails[{index}] must be an object")
        normalized = {**value, "delay_days": cadence[index]}
        try:
            messages.append(EmailMessage.model_validate(normalized))
        except ValidationError as exc:
            raise ValueError(f"emails[{index}] is invalid: {exc}") from exc
    return messages


async def generate_email_messages(
    brief: EmailCampaignBrief,
    *,
    provider: TextGenerationProvider,
) -> list[EmailMessage]:
    prompt = build_email_campaign_prompt(brief)
    raw = await provider.generate(prompt, n=brief.sequence_length)
    return parse_email_campaign_response(raw, brief)
