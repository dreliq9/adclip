# CLAUDE.md — adclip project context

## Product contract

adclip is a standalone, local-first, model-routed marketing creative
application. MCP is one interface adapter; it is not the architecture.

Read these before architectural changes:

- `docs/STANDALONE_ARCHITECTURE.md`
- `docs/MODEL_PROVIDERS.md`
- `docs/MODEL_ROUTING.md`

Binding rules:

- Core/domain/application modules must not import from `adclip.mcp`.
- CLI, MCP, and future HTTP/UI adapters call `AdclipApplication`.
- Workflows select capabilities and task routes, not vendor names.
- Route, provider, model, and generation options are separate values.
- Explicit provider/model values override a route primary.
- Provider adapters own vendor schemas; application and campaign code do not.
- Different model families require different request builders. Never restore a
  universal fal request dictionary.
- Route fallbacks are exposed metadata. Never silently execute another paid
  request after a failure.
- Routes needing unsupported inputs or adapters remain discoverable but must
  fail clearly until the capability is implemented.
- Existing CLI aliases, MCP tool names, briefs, and campaign exports remain
  compatible during migration.

## Current media routing

General image creative routes to fal-hosted `gpt-image-2` at medium quality.
Text-heavy creative raises quality; bulk work routes to FLUX.2 Pro; drafts use
Nano Banana 2 Lite; brand-controlled work uses FLUX.2 Flex. Premium image work
uses the direct OpenAI adapter.

General video routes to Kling O3 Standard. Premium video uses Veo 3.1,
multi-shot work uses Seedance 2 Fast, and budget work uses Wan 2.6.

Do not promote a route default because a model is fashionable. Run the fixed
bake-off fixtures and record quality, latency, cost, failures, and human scores.

## Evaluation policy

`adclip bakeoff` is dry-run by default. Paid execution requires `--execute` and
normal live-API authorization. The harness must record:

```text
fixture
route
provider
model
options
latency
cost
artifact SHA-256
evaluation dimensions
human score / notes
```

Keep fixtures stable enough for longitudinal comparison. Add a new fixture only
when it captures a materially different marketing failure mode.

## Runtime policy

Runtime modes:

```text
online
restricted_network
offline
air_gapped
```

`ADCLIP_ALLOWED_NETWORK_PROVIDERS` controls external access in restricted mode.
Potentially paid providers require `ADCLIP_ALLOW_LIVE_APIS=1`. Loopback text
inference is allowed offline and air-gapped; external endpoints are not.

## Configuration

```text
ADCLIP_TEXT_PROVIDER
ADCLIP_TEXT_MODEL
ADCLIP_IMAGE_ROUTE
ADCLIP_IMAGE_PROVIDER
ADCLIP_IMAGE_MODEL
ADCLIP_VIDEO_ROUTE
ADCLIP_VIDEO_PROVIDER
ADCLIP_VIDEO_MODEL
```

Provider-specific text settings include:

```text
ADCLIP_CLAUDE_MODEL
ADCLIP_ANTHROPIC_MODEL
ADCLIP_OPENAI_MODEL
ADCLIP_OPENAI_BASE_URL
ADCLIP_COMMAND_TEXT_COMMAND
ADCLIP_COMMAND_TEXT_MODEL
```

Direct OpenAI image access uses `ADCLIP_OPENAI_IMAGE_API_KEY` or
`OPENAI_API_KEY`. Do not add a vendor SDK when a stable HTTP contract is
sufficient.

## Built-in text paths

1. `claude-cli` — subscription-authenticated compatibility default.
2. `sampling` — sampling-capable MCP host.
3. `anthropic` — direct opt-in Anthropic API.
4. `openai-compatible` — local or hosted `/v1/chat/completions` endpoint.
5. `command` — local executable over stdin/stdout without a shell.
6. `fake` — deterministic test provider.

Legacy `LLM*` names and `llm_*` arguments remain compatibility aliases.

## Media adapters

- fal image: GPT Image 2, Nano Banana, FLUX.2, legacy aliases, raw endpoints
- direct OpenAI image: GPT Image API through the standard HTTP endpoint
- fal video: Kling, Veo, Seedance, Wan, legacy aliases, raw endpoints
- fake image/video: deterministic tests

Reference-image, vector, multi-reference video, image-animation, and existing
footage-edit routes are cataloged but intentionally non-executable until their
required input contracts and adapters exist.

## Vendored declip slice

`src/adclip/_video_backend.py` supplies legacy fal aliases and loudness logic.
It is a compatibility source, not the primary routing policy. Do not add
`declip` as a runtime dependency.

## Testing

Use fake providers and mocked HTTP. Required coverage includes:

- provider/model independence and compatibility aliases;
- task-route recommendation and explicit overrides;
- non-executable route rejection;
- family-specific request schemas for GPT Image, Nano Banana, FLUX, Kling,
  Veo, Seedance, and Wan;
- direct OpenAI image response handling;
- offline/air-gapped provider policy;
- unused media providers not being resolved;
- run-level route/provider/model provenance;
- dry-run bake-off making no provider call;
- CLI importing no module under `adclip.mcp`.

Do not require a live model server or paid API in the unit suite.

## Current scope

- Static, text, and 9:16 video creative
- Policy, healing, semantic review, and judging
- Transport-neutral `AdclipApplication`
- Model-agnostic text provider registry
- Task-oriented image and video route catalog
- Direct OpenAI image adapter
- Schema-aware fal image and video adapters
- Local HTTP and command-based text inference
- Recurring media bake-off harness
- Run-level route/provider/model provenance
- Standalone CLI and fourteen MCP tools

The next standalone milestone is S1: SQLite persistence, content-addressed
artifacts, stable IDs/Manifest v2, and durable resumable jobs. Route selection,
endpoint class, prompt version, generation parameters, cost, and artifact
hashes must become authoritative per-asset provenance.
