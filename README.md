# adclip

<!-- mcp-name: io.github.dreliq9/adclip -->

**Generate ad creative from a single JSON brief.** adclip is a standalone,
model-agnostic ad creative engine and MCP server that turns a structured brief
into ad copy, static images, and short-form video across Meta, Google,
LinkedIn, X, TikTok, and YouTube formats. Self-review loops filter for policy
violations and score variants before export.

The CLI and MCP server are sibling interfaces over the same application layer.
Core workflows do not require an MCP host, a particular model vendor, or
another Adam Engineering project. See
[`docs/STANDALONE_ARCHITECTURE.md`](docs/STANDALONE_ARCHITECTURE.md) for the
local-first product contract and
[`docs/MODEL_PROVIDERS.md`](docs/MODEL_PROVIDERS.md) for the provider/model
extension contract.

The compatibility default uses the `claude` CLI and its subscription auth, but
text provider and model are independent selections. Local or hosted
OpenAI-compatible endpoints, direct Anthropic, MCP sampling, and deterministic
test providers use the same workflow contract. Paid third-party providers are
opt-in and gated behind `ADCLIP_ALLOW_LIVE_APIS=1`.

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

Out:

- 2 × `meta_feed_4x5` composites (1080×1350, headline + body + CTA burned in)
- 2 × `google_rsa` text variants
- `manifest.json` with per-variant costs, policy flags, judge scores, and rationales
- A campaign directory ready for `adclip_export_dco` modular Meta export

## Install

```bash
pipx install adclip
```

Python 3.11+ is required. Install the Claude CLI only when using the
`claude-cli` compatibility default. The generic OpenAI-compatible adapter has
no additional Python dependency.

For the optional direct-Anthropic-API provider:

```bash
pipx install "adclip[anthropic]"
```

### From source

```bash
git clone https://github.com/dreliq9/adclip.git
cd adclip
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Standalone CLI

The CLI calls the application layer directly; it does not start or import the
MCP server.

```bash
adclip status                               # runtime + configured models
adclip formats                              # format specs
adclip estimate examples/taichi_brief.json  # cost preview
adclip copy examples/taichi_brief.json      # copy only
adclip run examples/taichi_brief.json --image fake
```

Provider and model can be selected independently:

```bash
adclip copy examples/taichi_brief.json \
  --provider openai-compatible \
  --model qwen2.5:14b

adclip run examples/taichi_brief.json \
  --text-provider openai-compatible \
  --text-model qwen2.5:14b \
  --image-provider fal \
  --image-model imagen-3 \
  --video-provider fal \
  --video-model veo-3.1
```

The former flags remain as aliases: `--llm`, `--llm-model`, `--image`, and
`--video`.

### Local inference

Any local service implementing `/v1/chat/completions` can supply text
generation:

```bash
export ADCLIP_TEXT_PROVIDER=openai-compatible
export ADCLIP_TEXT_MODEL=qwen2.5:14b
export ADCLIP_OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export ADCLIP_RUNTIME_MODE=offline

adclip copy examples/taichi_brief.json
```

Loopback inference is allowed in `offline` and `air_gapped` modes. A
non-loopback compatible endpoint is treated as external and potentially paid,
so normal network and billing authorization applies.

Connectivity can otherwise be constrained explicitly:

```bash
ADCLIP_RUNTIME_MODE=restricted_network \
ADCLIP_ALLOWED_NETWORK_PROVIDERS=claude-cli adclip status
```

Supported modes are `online`, `restricted_network`, `offline`, and
`air_gapped`. Paid providers still require `ADCLIP_ALLOW_LIVE_APIS=1`.

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

Then ask the host to generate variants from a brief. MCP generation tools also
accept separate provider and model arguments for text, image, and video.

### The three tools used most

- `adclip_generate_variants` — brief → copy → policy → media → render
- `adclip_generate_copy` — inexpensive copy-pool iteration
- `adclip_export_dco` — Meta modular-component export

<details>
<summary>All 12 tools</summary>

**Brief + inspection**

- `adclip_brief_validate`
- `adclip_estimate_cost`
- `adclip_list_formats`
- `adclip_policy_check`
- `adclip_campaign_status`

**Generation**

- `adclip_generate_copy`
- `adclip_generate_visuals`
- `adclip_generate_variants`

**Iteration**

- `adclip_render_variant`
- `adclip_regenerate`
- `adclip_score_variants`
- `adclip_export_dco`

</details>

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
| `stories_reels_9x16` | 9:16 | 1080×1920 | video¹ |
| `tiktok_9x16` | 9:16 | 1080×1920 | video¹ |
| `youtube_shorts_9x16` | 9:16 | 1080×1920 | video¹ |

¹ The current production video adapter uses fal.ai and then burns headline and
CTA overlays with FFmpeg. Select its model with `--video-model` or
`ADCLIP_VIDEO_MODEL`. Use `--video-provider fake` in tests.

## Text providers

| Provider | Key | Model behavior |
| --- | --- | --- |
| `default` / `claude-cli` | none | Explicit model or `ADCLIP_CLAUDE_MODEL`; default `sonnet` |
| `openai-compatible` | optional | Explicit model required; local or hosted `/v1/chat/completions` |
| `sampling` | none | Model selected by the sampling-capable MCP host |
| `anthropic` | key + live-API authorization | Explicit model or `ADCLIP_ANTHROPIC_MODEL` |
| `fake` | none | Deterministic test output |

Global configuration uses `ADCLIP_TEXT_PROVIDER` and `ADCLIP_TEXT_MODEL`.
Provider metadata declares model override support, structured-output behavior,
network scope, paid-API risk, and host-session requirements. Interface modules
do not contain vendor resolver branches.

## Media providers

The current image and video production provider is `fal`; `fake` is the local
test provider. Provider and model are already separate in application, CLI,
and MCP contracts:

```text
ADCLIP_IMAGE_PROVIDER
ADCLIP_IMAGE_MODEL
ADCLIP_VIDEO_PROVIDER
ADCLIP_VIDEO_MODEL
```

When a second production media provider is added, it should register behind the
same binding contract rather than adding campaign-level conditionals.

## Self-review loops

- **Judge** (`use_judge: true`) scores survivors on brief fit and copy quality.
- **Heal** (`heal_violations: N`) rewrites policy-violating candidates.
- **Semantic policy** (`use_semantic_policy: true`) checks paraphrases missed by
  literal rules.

These workflows consume the neutral text-generation contract and therefore use
the same selected model as copy generation.

## Live-API opt-in

`ADCLIP_ALLOW_LIVE_APIS=1` must be set before any potentially paid provider is
invoked. Provider-side billing gates remain as defense in depth. Merely having
a key in the environment is not authorization.

## Tests

```bash
.venv/bin/python -m pytest
```

## Status

The current standalone foundation includes a transport-neutral application
layer, provider/model separation, local OpenAI-compatible text inference,
selectable image and video models, explicit runtime modes, twelve MCP tools,
and CLI access. SQLite persistence, durable jobs, BrandKit/SourceLibrary, and
the local browser workbench are the next standalone milestones.
