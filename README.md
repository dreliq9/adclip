# adclip

<!-- mcp-name: io.github.dreliq9/adclip -->

**A standalone, model-routed marketing creative engine.** adclip turns a
structured campaign brief into policy-checked copy, static images, and
short-form video across Meta, Google, LinkedIn, X, TikTok, and YouTube formats.
It can be used through its CLI, MCP server, and future local web workbench.

adclip separates four concerns that are often conflated:

```text
creative task -> route -> provider adapter -> model + generation options
```

That means a campaign can ask for a **text-heavy image**, a **bulk draft**, or a
**premium video** without hard-coding one vendor throughout the workflow. The
route catalog selects a current primary and exposes ordered fallbacks; explicit
provider/model overrides remain authoritative.

See:

- [`docs/STANDALONE_ARCHITECTURE.md`](docs/STANDALONE_ARCHITECTURE.md)
- [`docs/MODEL_PROVIDERS.md`](docs/MODEL_PROVIDERS.md)
- [`docs/MODEL_ROUTING.md`](docs/MODEL_ROUTING.md)

## Current default routes

| Modality | Route | Primary | Purpose |
| --- | --- | --- | --- |
| Image | `general` | fal / `gpt-image-2` medium | General marketing creative, layout, and typography |
| Image | `text-heavy` | fal / `gpt-image-2` high | Posters, diagrams, packaging, and readable in-image text |
| Image | `bulk` | fal / `flux-2-pro` | Cost-controlled production batches |
| Image | `draft` | fal / `nano-banana-2-lite` | Fast concept exploration |
| Image | `brand-control` | fal / `flux-2-flex` | Controlled palettes and design-system work |
| Image | `premium` | direct OpenAI / `gpt-image-2` high | Highest-quality general render |
| Video | `general` | fal / `kling-o3-standard` | Practical social and performance-ad video |
| Video | `premium` | fal / `veo-3.1` | Cinematic output with native audio |
| Video | `multi-shot` | fal / `seedance-2-fast` | Directed multi-shot storytelling |
| Video | `budget` | fal / `wan-2.6` | Lower-cost video exploration |

Reference-image editing, vector generation, image-to-video, multi-reference
video, and footage editing are already cataloged as routes. They fail clearly
until the required inputs or provider adapters are implemented rather than
pretending the current brief schema can support them.

## What a run looks like

Brief in (`examples/taichi_brief.json`):

```json
{
  "product": "Taichi crypto trading bot",
  "value_prop": "Paper-trade our signals before risking real cash.",
  "audience": "Skeptical retail crypto traders.",
  "angles": ["credibility", "curiosity"],
  "tone": "confident, dry, no hype",
  "cta": "Start paper trading",
  "formats": ["meta_feed_4x5", "google_rsa"],
  "variants": 2,
  "policy_profile": "crypto",
  "must_avoid": ["guaranteed returns"],
  "use_judge": true,
  "heal_violations": 2,
  "output_dir": "/tmp/adclip_out"
}
```

A run produces a portable campaign directory containing the original brief,
copy, raw media, rendered assets, rejected candidates, costs, scores, and the
selected route/provider/model provenance.

## Install

```bash
pipx install adclip
```

Python 3.11+ is required. The default text path uses the Claude CLI subscription
if installed. Local command and OpenAI-compatible text providers require no
additional Python SDK. Direct Anthropic remains optional:

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
```

### Route-driven generation

```bash
# Current general defaults: GPT Image 2 through fal + Kling O3 through fal
adclip run brief.json

# Explicit task routes
adclip run brief.json \
  --image-route text-heavy \
  --video-route premium

# Explicit values override route primaries
adclip run brief.json \
  --image-route general \
  --image-provider openai \
  --image-model gpt-image-2 \
  --video-route budget \
  --video-provider fal \
  --video-model wan-2.6
```

The compatibility flags remain:

```text
--llm          -> --text-provider
--llm-model    -> --text-model
--image        -> --image-provider
--video        -> --video-provider
```

## Recurring model bake-off

Model defaults should be promoted by evidence rather than reputation. adclip
ships fixed image and video marketing fixtures covering typography, realism,
brand color, package fidelity, product stability, audio, and multi-shot
continuity.

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

The result records provider, model, route options, latency, estimated cost,
artifact SHA-256, evaluation dimensions, and placeholders for human scoring.
No automatic paid fallback is performed.

## Text providers

| Provider | Model behavior | Runtime |
| --- | --- | --- |
| `default` / `claude-cli` | Explicit model or `ADCLIP_CLAUDE_MODEL`; default `sonnet` | External through Claude CLI |
| `openai-compatible` | Explicit model required | Local loopback or external compatible HTTP |
| `command` | Any local executable reading stdin and writing stdout | Offline and air-gapped capable |
| `sampling` | Host selects model | Sampling-capable MCP host required |
| `anthropic` | Explicit model or `ADCLIP_ANTHROPIC_MODEL` | External and potentially paid |
| `fake` | Deterministic identity | In-process testing |

### Local HTTP inference

```bash
export ADCLIP_TEXT_PROVIDER=openai-compatible
export ADCLIP_TEXT_MODEL=qwen2.5:14b
export ADCLIP_OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export ADCLIP_RUNTIME_MODE=offline
adclip copy brief.json
```

### Local command inference

```bash
export ADCLIP_TEXT_PROVIDER=command
export ADCLIP_COMMAND_TEXT_COMMAND='my-model-cli --model {model} --json'
export ADCLIP_COMMAND_TEXT_MODEL=my-local-model
export ADCLIP_RUNTIME_MODE=air_gapped
adclip copy brief.json
```

The command provider sends the prompt through stdin, reads stdout, and never
invokes a shell.

## Media providers and models

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

- `fal`: GPT Image 2, Nano Banana, FLUX.2, legacy aliases, and raw fal endpoints
- `openai`: first-party GPT Image API
- `fake`: deterministic test image

Video providers:

- `fal`: Kling O3/3, Veo 3.1, Seedance 2, Wan 2.6, legacy aliases, raw endpoints
- `fake`: deterministic test video

Each supported fal model family has its own request builder. adclip does not
assume that GPT Image, Nano Banana, FLUX, Kling, Veo, Seedance, and Wan share a
single request schema.

## MCP usage

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

The MCP surface contains the original campaign tools plus route discovery:

- `adclip_brief_validate`
- `adclip_estimate_cost`
- `adclip_list_formats`
- `adclip_list_media_routes`
- `adclip_recommend_media_route`
- `adclip_policy_check`
- `adclip_generate_copy`
- `adclip_generate_visuals`
- `adclip_generate_variants`
- `adclip_render_variant`
- `adclip_regenerate`
- `adclip_score_variants`
- `adclip_campaign_status`
- `adclip_export_dco`

## Formats

| Name | Aspect | Size | Kind |
| --- | --- | --- | --- |
| `meta_feed_1x1` | 1:1 | 1080×1080 | static |
| `meta_feed_4x5` | 4:5 | 1080×1350 | static |
| `google_display_square` | 1:1 | 1200×1200 | static |
| `google_display_landscape` | 1.91:1 | 1200×628 | static |
| `linkedin_single` | 1.91:1 | 1200×627 | static |
| `x_promoted` | 16:9 | 1200×675 | static |
| `google_rsa` | text | — | text |
| `stories_reels_9x16` | 9:16 | 1080×1920 | video |
| `tiktok_9x16` | 9:16 | 1080×1920 | video |
| `youtube_shorts_9x16` | 9:16 | 1080×1920 | video |

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

Fallbacks are metadata, not an instruction to spend again automatically. A
caller must deliberately select or authorize another target.

## Tests

```bash
.venv/bin/python -m pytest
```

## Status

The standalone foundation now includes a transport-neutral application layer,
model-agnostic text providers, task-oriented image/video routes, direct OpenAI
image access, schema-aware fal adapters, run-level model provenance, a
repeatable bake-off harness, fourteen MCP tools, and CLI access. SQLite,
durable jobs, BrandKit/SourceLibrary, platform performance feedback, and the
local browser workbench remain the next major milestones.
