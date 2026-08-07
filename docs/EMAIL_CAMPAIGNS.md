# Email Campaign and HTML Editing

**Status:** Initial standalone vertical slice  
**Date:** 2026-08-07

## Product boundary

adclip owns email campaign authoring and portable campaign artifacts:

```text
campaign brief
  -> provider-neutral sequence generation
  -> structured editable message documents
  -> responsive HTML + plain text
  -> lint and compliance metadata
  -> portable export
```

Sending is intentionally a separate connector boundary. The initial slice does
not require or assume Mailchimp, Klaviyo, SendGrid, Amazon SES, Gmail, or any
other email service provider.

Future deployment adapters should consume the exported message body, headers,
list metadata, and provider-independent campaign manifest. They must not become
the source of truth for email content.

## Why native HTML first

The initial renderer emits conservative, table-based, mostly inline-styled
email HTML. It has no Node.js runtime dependency and remains usable in local and
air-gapped installations.

MJML is a valuable optional interchange and compilation target. Its official
documentation describes responsive sections/columns, accessibility metadata,
preview text, and strict validation. A future MJML adapter may import or export
MJML, but the baseline adclip workflow must remain usable without it:

- https://documentation.mjml.io/

Gmail supports inline style blocks, standard CSS, and supported media queries,
but can ignore unsupported properties and selectors. The adclip linter therefore
warns about fragile browser-oriented layout techniques rather than treating a
normal web page as valid email HTML:

- https://developers.google.com/workspace/gmail/design/css

## Domain models

`EmailCampaignBrief` describes:

- campaign name and type;
- product, value proposition, audience, objective, offer, tone, and CTA;
- sender identity and reply-to address;
- sequence length and cadence;
- brand colors and logo;
- landing page, unsubscribe, and postal-address values;
- must-include and must-avoid terms;
- output directory.

`EmailMessage` contains subject, preheader, delay, tags, and stable blocks.

Supported block kinds:

```text
heading
paragraph
image
button
divider
spacer
raw_html
```

Every block has a stable ID. The renderer emits matching comments:

```html
<!-- adclip:block:headline:start -->
...
<!-- adclip:block:headline:end -->
```

Those markers let adclip patch rendered HTML without relying on brittle visual
coordinates.

## Editing

Two edit surfaces use the same patch vocabulary:

1. structured `EmailMessage` JSON;
2. rendered HTML with adclip block markers.

Operations:

```text
replace_text
set_link
set_image
replace_block_html
remove_block
```

Raw replacement HTML is screened for active or form-capable elements. Scripts,
iframes, forms, inputs, embedded objects, audio/video elements, and
`javascript:` URLs are rejected.

## Rendering and exports

A generated campaign directory contains:

```text
campaign.json
manifest.json
emails/
  01-email-01/
    message.json
    email.html
    email.txt
    headers.json
    lint.json
```

The renderer emits:

- a 600-pixel responsive presentation-table layout;
- inline styles plus a small mobile media query;
- hidden preheader text;
- accessible image alternatives;
- a plain-text alternative;
- stable block-editing markers;
- marketing footer and unsubscribe link;
- portable header metadata.

## Linting

The built-in linter checks:

- blocked active/form tags;
- `javascript:` URLs;
- missing image `src` or `alt`;
- missing link destinations;
- insecure remote asset and link URLs;
- missing document language;
- absence of presentation-table semantics;
- fragile flex/grid/absolute/fixed CSS;
- subject and preheader length;
- plain-text alternative;
- visible unsubscribe treatment;
- postal-address field;
- `List-Unsubscribe` and `List-Unsubscribe-Post` headers;
- unresolved template tokens.

The linter does not claim to replace rendering tests in Gmail, Outlook, Apple
Mail, or a dedicated compatibility service. It is a fail-fast authoring gate.

## Sender and unsubscribe metadata

For marketing campaigns, adclip exports:

```text
List-Unsubscribe: <{{unsubscribe_url}}>
List-Unsubscribe-Post: List-Unsubscribe=One-Click
```

Gmail's sender guidelines require one-click unsubscribe for qualifying
high-volume marketing/subscribed mail and require a visible unsubscribe option
in the message. Yahoo documents the same RFC 8058 header form:

- https://support.google.com/mail/answer/81126
- https://senders.yahooinc.com/subhub/

adclip produces the metadata, but an eventual sending adapter is responsible for
substituting a recipient-specific HTTPS unsubscribe URL, authenticating the
sending domain, and delivering the exact exported headers.

## CLI

Generate and export a campaign:

```bash
adclip email generate campaign-brief.json \
  --provider openai-compatible \
  --model qwen2.5:14b
```

Render one structured message:

```bash
adclip email render campaign-brief.json message.json \
  --output-dir ./rendered-email
```

Lint imported or rendered HTML:

```bash
adclip email lint email.html \
  --context lint-context.json \
  --plain-text email.txt
```

Patch HTML:

```bash
adclip email patch-html email.html patches.json \
  --context lint-context.json \
  --output email-edited.html
```

Patch the structured document:

```bash
adclip email patch-message message.json patches.json \
  --output message-edited.json
```

## MCP

The email tool surface is:

```text
adclip_email_generate_campaign
adclip_email_render
adclip_email_lint
adclip_email_patch_html
adclip_email_patch_message
```

The generation tool uses the same provider/model registry as ad copy. Rendering,
linting, and patching are local deterministic operations.

## Example brief

```json
{
  "name": "Widget launch",
  "product": "Widget",
  "value_prop": "Test new workflows in minutes.",
  "audience": "Small product teams",
  "objective": "Drive qualified trials",
  "tone": "specific, practical, no hype",
  "offer": "14-day trial",
  "cta": "Start the trial",
  "landing_page_url": "https://example.com/trial",
  "sender_name": "Acme",
  "sender_email": "hello@example.com",
  "campaign_type": "marketing",
  "sequence_length": 3,
  "cadence_days": [0, 2, 5],
  "brand_colors": ["#111827", "#2563EB", "#F3F4F6"],
  "unsubscribe_url": "{{unsubscribe_url}}",
  "physical_address": "{{physical_address}}",
  "output_dir": "./widget-email-campaign"
}
```

## Example patch

```json
[
  {
    "block_id": "body_1",
    "op": "replace_text",
    "find": "Old sentence",
    "value": "New sentence"
  },
  {
    "block_id": "cta",
    "op": "set_link",
    "href": "https://example.com/new-offer"
  }
]
```

## Next email milestones

- BrandKit-driven email styles and reusable templates
- campaign objectives and segment-specific variants
- subject/preheader bake-offs
- MJML import/export adapter
- screenshot and client-render testing adapters
- link tracking and UTM policy
- suppression-list and consent metadata
- provider-neutral send plan
- draft-only ESP adapters
- performance ingestion and next-test recommendations
