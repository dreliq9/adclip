# adclip

<!-- mcp-name: io.github.dreliq9/adclip -->

**A standalone, model-routed marketing creative engine.** adclip turns a
structured campaign brief into policy-checked copy, static images, short-form
video, and responsive email campaigns for Meta, Google, LinkedIn, X, TikTok,
YouTube, and inbox delivery. It can be used through its CLI, MCP server, and
future local web workbench.

adclip deliberately separates:

```text
marketing task -> route/capability -> provider adapter -> model + options
```

A campaign can request a text-heavy image, a bulk draft, a premium video, or a
multi-message email sequence without hard-coding one vendor throughout the
workflow. Routes select a current primary and expose ordered fallbacks;
explicit provider/model overrides remain authoritative. Fallbacks are never run
silently because another attempt may incur additional cost.

Architecture references:

- [`docs/STANDALONE_ARCHITECTURE.md`](docs/STANDALONE_ARCHITECTURE.md)
- [`docs/MODEL_PROVIDERS.md`](docs/MODEL_PROVIDERS.md)
- [`docs/MODEL_ROUTING.md`](docs/MODEL_ROUTING.md)
- [`docs/EMAIL_CAMPAIGNS.md`](docs/EMAIL_CAMPAIGNS.md)
- [`docs/GROK_BUILD_CREATIVE_WORKFLOW.md`](docs/GROK_BUILD_CREATIVE_WORKFLOW.md) — Grok Build Imagine + review–regen loop
- [`docs/CREATIVE_AUDIT_TEMPLATE.md`](docs/CREATIVE_AUDIT_TEMPLATE.md) — performance creative audit template

## Current routes

| Modality | Route | Primary | Purpose |
| --- | --- | --- | --- |
| Image | `general` | fal / `gpt-image-2` medium | General marketing creative, layout, typography |
| Image | `text-heavy` | fal / `gpt-image-2` high | Posters, diagrams, packaging, readable text |
| Image | `bulk` | fal / `flux-2-pro` | Cost-controlled production batches |
| Image | `draft` | fal / `nano-banana-2-lite` | Fast concept exploration |
| Image | `brand-control` | fal / `flux-2-flex` | Controlled palettes and layouts |
| Image | `premium` | direct OpenAI / `gpt-image-2` high | Highest-quality general render |
| Video | `general` | fal / `kling-o3-standard` | Practical performance and social video |
| Video | `premium` | fal / `veo-3.1` | Cinematic output with native audio |
| Video | `multi-shot` | fal / `seedance-2-fast` | Directed multi-shot storytelling |
| Video | `budget` | fal / `wan-2.7` | Lower-cost, flexible-duration exploration |

Reference-image editing, vectors, image-to-video, multi-reference video, and
footage editing are already cataloged. They fail clearly until the required
input contracts and provider adapters exist rather than pretending the current
brief schema can support them.

## Install

```bash
pipx install adclip
```

Python 3.11+ is required. Direct Anthropic remains optional:

```bash
pipx install "adclip[anthropic]"
```

From source:

```bash
git clone https://github.com/dreliq9/adclip.git
cd adclip
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Standalone CLI

```bash
adclip status
adclip formats
adclip routes
adclip routes --modality image
adclip route-recommend image --text-heavy
adclip estimate examples/taichi_brief.json
adclip copy examples/taichi_brief.json
adclip run examples/taichi_brief.json --image-provider fake
adclip email --help
```

### Routed generation

```bash
# General defaults: GPT Image 2 through fal + Kling O3 through fal
adclip run brief.json

# Task-specific routes
adclip run brief.json \
  --image-route text-heavy \
  --video-route premium

# Explicit provider/model values override route primaries
adclip run brief.json \
  --image-route general \
  --image-provider openai \
  --image-model gpt-image-2 \
  --video-route budget \
  --video-provider fal \
  --video-model wan-2.7
```

Compatibility aliases remain:

```text
--llm          -> --text-provider
--llm-model    -> --text-model
--image        -> --image-provider
--video        -> --video-provider
```

## Email campaigns and HTML editing

Email is a native standalone capability, not a wrapper around one email service
provider.

```bash
# Generate a sequence and portable campaign bundle
adclip email generate email-brief.json \
  --provider openai-compatible \
  --model qwen2.5:14b

# Render one structured message
adclip email render email-brief.json message.json \
  --output-dir ./rendered-email

# Lint imported or generated HTML
adclip email lint email.html \
  --context lint-context.json \
  --plain-text email.txt

# Patch rendered HTML by stable block ID
adclip email patch-html email.html patches.json \
  --context lint-context.json \
  --output email-edited.html

# Patch the source message document before rendering
adclip email patch-message message.json patches.json \
  --output message-edited.json
```

A generated email campaign contains:

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

The renderer emits conservative table-based responsive HTML, hidden preheader
text, a plain-text alternative, stable block-editing markers, and marketing
footer/header metadata. The linter checks active content, unsafe URLs, missing
alt text and links, fragile CSS, subject/preheader length, unsubscribe and postal
address treatment, one-click unsubscribe headers, and unresolved template
tokens.

Sending remains a connector boundary. Future ESP adapters will consume the
portable bundle rather than own the email document. See
[`docs/EMAIL_CAMPAIGNS.md`](docs/EMAIL_CAMPAIGNS.md).

## Recurring model bake-off

Defaults should be promoted by evidence rather than reputation. adclip ships
stable marketing fixtures covering typography, realism, brand color, package
fidelity, product stability, audio/lip sync, and multi-shot continuity.

A bake-off is a **dry run by default**:

```bash
adclip bakeoff \
  --modality image \
  --routes general,text-heavy,bulk,draft \
  --output-dir ./image-bakeoff
```

This writes `plan.json` without calling a paid provider. Execution requires an
additional flag and still passes through the live-API authorization gate:

```bash
ADCLIP_ALLOW_LIVE_APIS=1 adclip bakeoff \
  --modality image \
  --routes general,text-heavy,bulk \
  --repetitions 3 \
  --execute \
  --output-dir ./image-bakeoff
```

Results record route, provider, model, options, latency, estimated cost,
artifact SHA-256, failure status, evaluation dimensions, and placeholders for
human scoring.

## Text providers

| Provider | Intended use |
| --- | --- |
| `claude-cli` | Existing subscription-authenticated compatibility default |
| `openai-compatible` | Local or hosted `/v1/chat/completions` endpoint |
| `command` | Any local executable reading stdin and writing stdout |
| `sampling` | Sampling-capable MCP host |
| `anthropic` | Direct opt-in Anthropic API |
| `fake` | Deterministic testing |

Local HTTP inference:

```bash
export ADCLIP_TEXT_PROVIDER=openai-compatible
export ADCLIP_TEXT_MODEL=qwen2.5:14b
export ADCLIP_OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export ADCLIP_RUNTIME_MODE=offline
adclip copy brief.json
```

Local command inference:

```bash
export ADCLIP_TEXT_PROVIDER=command
export ADCLIP_COMMAND_TEXT_COMMAND='my-model-cli --model {model} --json'
export ADCLIP_COMMAND_TEXT_MODEL=my-local-model
export ADCLIP_RUNTIME_MODE=air_gapped
adclip copy brief.json
```

The command provider sends the prompt through stdin, reads stdout, and never
invokes a shell.

## Media adapters

Primary configuration:

```text
ADCLIP_IMAGE_ROUTE
ADCLIP_IMAGE_PROVIDER
ADCLIP_IMAGE_MODEL
ADCLIP_VIDEO_ROUTE
ADCLIP_VIDEO_PROVIDER
ADCLIP_VIDEO_MODEL
```

Image providers:

- `fal`: GPT Image 2, Nano Banana, FLUX.2, legacy aliases, raw fal endpoints
- `openai`: first-party GPT Image API
- `fake`: deterministic test image

Video providers:

- `fal`: Kling O3/3, Veo 3.1, Seedance 2, Wan 2.7, Wan 2.6 legacy, raw endpoints
- `fake`: deterministic test video

Each model family has its own request builder. adclip does not assume GPT Image,
Nano Banana, FLUX, Kling, Veo, Seedance, and Wan accept one universal schema.

## MCP

Add to `.mcp.json` or `~/.claude.json`:

```json
{
  "mcpServers": {
    "adclip": {
      "command": "adclip-mcp"
    }
  }
}
```

The MCP surface includes campaign generation and iteration plus:

- `adclip_list_media_routes`
- `adclip_recommend_media_route`
- routed cost estimation
- routed full generation
- routed visual-only generation
- routed regeneration
- `adclip_email_generate_campaign`
- `adclip_email_render`
- `adclip_email_lint`
- `adclip_email_patch_html`
- `adclip_email_patch_message`

## Runtime and billing safety

Supported modes:

```text
online
restricted_network
offline
air_gapped
```

Loopback inference is allowed offline. External providers are refused in
offline and air-gapped modes. Potentially paid providers require:

```bash
ADCLIP_ALLOW_LIVE_APIS=1
```

Email rendering, linting, and patching are local deterministic operations.
Email generation uses the normal text-provider policy. No sending provider is
invoked by the initial email slice.

## Tests

```bash
.venv/bin/python -m pytest
```

## Status

The current foundation includes a transport-neutral application layer,
model-agnostic text providers, task-oriented image/video routes, direct OpenAI
image access, schema-aware fal adapters, run-level model provenance, a
repeatable bake-off harness, responsive email campaign generation and editing,
and CLI/MCP access. SQLite, durable jobs, BrandKit/SourceLibrary, send-platform
connectors, performance feedback, and the local browser workbench remain the
next major milestones.
