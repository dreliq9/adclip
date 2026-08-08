# adclip

<!-- mcp-name: io.github.dreliq9/adclip -->

**An open, standalone, model-routed marketing creative and learning engine.**

adclip turns campaign intent into policy-checked copy, static creative,
short-form video, and responsive email; preserves exact creative lineage; reads
performance back from deployed creative; and structures that evidence into
explicit experiments and next-test recommendations.

```text
brief
  -> copy / image / video / email
  -> exact creative artifacts + provenance
  -> deployment lineage
  -> performance observations
  -> experiment evidence
  -> next test
```

MCP is one interface into adclip, not the architecture. The same application
services are available to the standalone CLI and are intended to back a future
local browser workbench.

## Why adclip exists

Most AI marketing stacks split the workflow across a copy tool, image/video
generators, an email platform, ad-platform dashboards, and creative analytics.
adclip's goal is to keep the **campaign model, creative lineage, and learning
loop portable**, while letting model providers and delivery platforms remain
replaceable adapters.

Core principles:

- **Model-neutral:** workflows request capabilities/routes rather than hard-code
  one model vendor.
- **Standalone:** CLI workflows do not require an MCP host.
- **Local-first:** local command and OpenAI-compatible inference can run offline
  or air-gapped when configured appropriately.
- **Portable:** campaign artifacts, email HTML/text, manifests, deployment
  mappings, observations, and experiments remain inspectable files.
- **Evidence-aware:** observational rankings are not silently presented as
  causal lift.
- **Spend-safe:** paid generation is opt-in and route fallbacks are not silently
  executed.

## Start here

- **[Quickstart](docs/QUICKSTART.md)** — zero-cost DTC creative, email, and learning walkthrough.
- **[Examples](examples/README.md)** — marketer-facing campaign portfolio.
- **[Documentation index](docs/README.md)** — architecture and capability docs.
- **[LLM guidance](LLM.md)** — model-neutral contributor/agent contract.

Install from PyPI:

```bash
pipx install adclip
```

The PyPI release can lag the current repository. For the exact `main` feature
set documented here, install from source:

```bash
git clone https://github.com/dreliq9/adclip.git
cd adclip
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Python 3.11+ is required.

## Five-minute zero-cost demo

Generate a fictional DTC skincare launch across Meta, Reels/TikTok, and Google
using only fake creative providers:

```bash
adclip run examples/01-dtc-skincare/brief.json \
  --text-provider fake \
  --image-provider fake \
  --video-provider fake
```

Render the matching checked-in launch email without a model call:

```bash
adclip email render \
  examples/01-dtc-skincare/email_brief.json \
  examples/01-dtc-skincare/email_message.json \
  --output-dir ./adclip_skincare_email_render
```

Build a complete synthetic creative-test bundle:

```bash
python examples/06-creative-experiment/build_demo.py
```

Then inspect the evidence:

```bash
adclip performance report ./adclip_creative_test_demo \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion
```

The builder prints an experiment ID that can be passed to
`experiment-evaluate` and `next-test`. None of the commands above need a paid
model API or live ad account.

## Example portfolio

The repository examples are organized around marketing problems rather than
internal subsystems:

| Example | Marketing workload | Main surfaces |
| --- | --- | --- |
| `01-dtc-skincare` | Product launch / first purchase | Meta, Reels, TikTok, Google, email |
| `02-b2b-saas-lead-gen` | Qualified demo generation | LinkedIn, Google Search |
| `03-local-service-lead-gen` | Local direct-response leads | Meta, Google Search |
| `04-subscription-winback` | Lifecycle retention | Email |
| `05-mobile-app-acquisition` | Free-trial acquisition | TikTok, Reels, Shorts, Meta |
| `06-creative-experiment` | Controlled hook learning | Synthetic Meta observations |

See [examples/README.md](examples/README.md) for the business goal, audience,
hypothesis, and commands behind each case.

## Current capability map

| Area | Current capability |
| --- | --- |
| Campaign briefs | Structured `AdBrief`, formats, policy constraints, cost estimation |
| Copy | Provider-neutral generation, filtering, scoring, healing/judge compatibility |
| Images | Task routes over fal/direct OpenAI/fake adapters with model-family schemas |
| Video | Routed fal/fake generation for short-form formats |
| Model selection | Explicit route/provider/model/options separation and bake-offs |
| Email | Sequence generation, structured blocks, responsive HTML/text, headers, lint, patching |
| Lineage | Stable campaign IDs and artifact-bound creative IDs |
| Performance | Explicit deployment mappings and read-only Meta Insights sync |
| Reporting | Attribution-safe exact windows and descriptive creative comparison |
| Experiments | Control/treatment artifacts, changed factor, thresholds, rate confidence intervals |
| Learning | Supported/contradicted/inconclusive evidence and deterministic next-test actions |
| Interfaces | CLI + MCP over shared application services |
| Safety | Runtime network modes, paid-generation gate, read-only Meta connector |

## Standalone CLI

Useful discovery commands:

```bash
adclip status
adclip formats
adclip routes
adclip routes --modality image
adclip route-recommend image --text-heavy
adclip estimate examples/01-dtc-skincare/brief.json
adclip email --help
adclip performance --help
```

### Routed creative generation

```bash
# Route defaults
adclip run brief.json

# Task-specific selection
adclip run brief.json \
  --image-route text-heavy \
  --video-route premium

# Explicit provider/model overrides remain authoritative
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

## Current media routes

| Modality | Route | Primary | Purpose |
| --- | --- | --- | --- |
| Image | `general` | fal / `gpt-image-2` medium | General marketing creative |
| Image | `text-heavy` | fal / `gpt-image-2` high | Readable text/layout work |
| Image | `bulk` | fal / `flux-2-pro` | Cost-controlled batches |
| Image | `draft` | fal / `nano-banana-2-lite` | Fast exploration |
| Image | `brand-control` | fal / `flux-2-flex` | Palette/layout control |
| Image | `premium` | direct OpenAI / `gpt-image-2` high | Premium general render |
| Video | `general` | fal / `kling-o3-standard` | General social/performance video |
| Video | `premium` | fal / `veo-3.1` | Cinematic/native-audio work |
| Video | `multi-shot` | fal / `seedance-2-fast` | Directed multi-shot storytelling |
| Video | `budget` | fal / `wan-2.7` | Lower-cost exploration |

Reference-image, vector, multi-reference, image-animation, and footage-edit
routes are cataloged but remain non-executable until their required input
contracts/adapters exist. See [Model routing](docs/MODEL_ROUTING.md).

## Email campaigns and HTML editing

Email is native campaign state rather than a wrapper around one ESP.

```bash
# Render the canonical launch message locally
adclip email render \
  examples/01-dtc-skincare/email_brief.json \
  examples/01-dtc-skincare/email_message.json \
  --output-dir ./rendered-email

# Apply stable block-level edits to a generic fixture
adclip email patch-message \
  examples/email_message.json \
  examples/email_patches.json \
  --output ./message-edited.json
```

Generated campaigns contain portable message JSON, responsive HTML, plain text,
headers, lint reports, and a manifest. Sequence generation uses a configured
text provider; the generic `fake` text provider is a copy-generation fixture,
not an email-sequence generator. Sending, consent, suppression, and ESP account
state remain connector responsibilities.

See [Email campaigns](docs/EMAIL_CAMPAIGNS.md).

## Performance and creative learning

adclip can map an exact local creative to an existing Meta ad and read Insights
back without adding Meta mutation methods.

```bash
adclip performance link-meta ./campaign \
  --variant-id v01 \
  --account-id act_123456 \
  --ad-id 987654321

export ADCLIP_META_ACCESS_TOKEN=...

adclip performance sync-meta ./campaign \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion
```

Measurement windows are keyed by `(since, until, action_report_time)`, so
conversion- and impression-attributed rows for the same dates are not silently
combined.

Descriptive comparison:

```bash
adclip performance compare ./campaign \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion \
  --metric ctr
```

See [Performance learning](docs/PERFORMANCE_LEARNING.md).

## Explicit creative experiments

The checked-in demo uses a familiar paid-social question: does vivid problem
framing beat a plain product-benefit hook?

```bash
python examples/06-creative-experiment/build_demo.py
```

Or declare your own experiment before interpreting results:

```bash
adclip performance experiment-create ./campaign \
  --name "Hook CTR test" \
  --hypothesis "Problem framing increases CTR" \
  --changed-factor hook \
  --control-variant v01 \
  --treatment-variant v02 \
  --control-value "plain benefit" \
  --treatment-value "problem framing" \
  --metric ctr
```

Current inferential verdicts are deliberately limited to rate metrics with
explicit aggregate numerators/denominators: CTR, outbound CTR, and action rate.
CPA and ROAS remain descriptive without variance/event-level evidence.
Observational comparisons remain inconclusive by design, and experiment outputs
currently keep `causal_claim: false`.

See [Experiment contract](docs/EXPERIMENTS.md).

## Recurring model bake-offs

Defaults should be promoted by evidence rather than reputation.

```bash
# Dry-run plan only
adclip bakeoff \
  --modality image \
  --routes general,text-heavy,bulk,draft \
  --output-dir ./image-bakeoff
```

Live execution requires both `--execute` and normal paid-provider authorization.
Results record route, provider, model, options, latency, estimated cost,
artifact SHA-256, failures, evaluation dimensions, and human-review fields.

## Text providers

| Provider | Intended use |
| --- | --- |
| `claude-cli` | Subscription-authenticated compatibility default |
| `openai-compatible` | Local or hosted `/v1/chat/completions` endpoint |
| `command` | Local executable over stdin/stdout |
| `sampling` | Sampling-capable MCP host |
| `anthropic` | Direct opt-in Anthropic API |
| `fake` | Deterministic copy tests/examples |

Local HTTP inference:

```bash
export ADCLIP_TEXT_PROVIDER=openai-compatible
export ADCLIP_TEXT_MODEL=qwen2.5:14b
export ADCLIP_OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export ADCLIP_RUNTIME_MODE=offline
adclip copy examples/01-dtc-skincare/brief.json
```

See [Model providers](docs/MODEL_PROVIDERS.md).

## MCP

Example local registration:

```json
{
  "mcpServers": {
    "adclip": {
      "command": "adclip-mcp"
    }
  }
}
```

The MCP surface exposes the same campaign, routing, email, performance, and
experiment application services used by the CLI. Important newer tools include:

```text
adclip_list_media_routes
adclip_recommend_media_route
adclip_email_generate_campaign
adclip_email_render
adclip_email_lint
adclip_email_patch_html
adclip_email_patch_message
adclip_performance_link_meta
adclip_performance_deployments
adclip_performance_sync_meta
adclip_performance_report
adclip_performance_compare
adclip_experiment_create
adclip_experiments
adclip_experiment_evaluate
adclip_experiment_next_test
```

## Runtime and billing safety

Supported runtime modes:

```text
online
restricted_network
offline
air_gapped
```

External generation providers are refused offline/air-gapped. Loopback text
inference remains available. Potentially paid generation requires:

```bash
ADCLIP_ALLOW_LIVE_APIS=1
```

The Meta performance connector is a separate read-only network adapter and does
not use the generation-spend authorization flag.

## Tests

The project test suite is designed to run without paid APIs or live marketing
accounts:

```bash
python -m pytest
python -m compileall src/adclip
```

## Current status and next milestones

The current core includes generation, email authoring, exact creative lineage,
read-only Meta performance ingestion, attribution-safe reporting, explicit
experiments, and next-test recommendations.

The largest remaining product gaps are:

1. SQLite/migrations as authoritative state, content-addressed artifacts, and
   durable resumable jobs;
2. BrandKit and SourceLibrary;
3. bundled local browser workbench;
4. creative-attribute extraction and experiment-aware controlled generation;
5. Google Ads, TikTok, and ESP performance adapters;
6. fatigue/change-point analysis and richer CPA/ROAS evidence;
7. separately authorized draft/paused deployment workflows.

See [Standalone architecture](docs/STANDALONE_ARCHITECTURE.md) for the roadmap.
