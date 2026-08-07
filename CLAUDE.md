# CLAUDE.md — adclip project context

## Product contract

adclip is a standalone, local-first, model-routed marketing creative
application. MCP is one interface adapter; it is not the architecture.

Read before architectural changes:

- `docs/STANDALONE_ARCHITECTURE.md`
- `docs/MODEL_PROVIDERS.md`
- `docs/MODEL_ROUTING.md`
- `docs/EMAIL_CAMPAIGNS.md`

Binding rules:

- Core/domain/application modules must not import from `adclip.mcp`.
- CLI, MCP, and future HTTP/UI adapters call application-layer services.
- Workflows select capabilities and task routes, not vendor names.
- Route, provider, model, and generation options are separate values.
- Explicit provider/model values override route primaries.
- Provider adapters own vendor schemas; campaign and interface code do not.
- Different model families require distinct request builders. Never restore a
  universal fal request dictionary.
- Route fallbacks are visible metadata. Never silently execute another paid
  request after failure.
- Unsupported routes remain discoverable but must fail clearly until their
  required input contract and adapter exist.
- Email rendering/editing is native and send-provider-neutral. Do not put
  campaign document state inside an ESP adapter.
- Existing CLI aliases, MCP tool names, briefs, and campaign exports remain
  compatible during migration.

## Current routing policy

Image:

```text
general       fal / gpt-image-2 medium
text-heavy    fal / gpt-image-2 high
bulk          fal / flux-2-pro
draft         fal / nano-banana-2-lite
brand-control fal / flux-2-flex
premium       direct OpenAI / gpt-image-2 high
```

Video:

```text
general       fal / kling-o3-standard
premium       fal / veo-3.1
multi-shot    fal / seedance-2-fast
budget        fal / wan-2.7
```

Wan 2.6 remains a legacy compatibility alias and budget-route fallback. Do not
promote a route because a model is fashionable; use the fixed bake-off fixtures
and record quality, latency, cost, failure rate, and human preference.

## Email campaign architecture

Email follows:

```text
EmailCampaignBrief
  -> provider-neutral sequence generation
  -> EmailMessage blocks
  -> HTML + text + headers
  -> lint/compliance report
  -> portable campaign bundle
```

The initial email implementation lives under:

```text
src/adclip/email/
src/adclip/application/email_services.py
src/adclip/mcp/email_tools.py
```

Rules:

- `EmailMessage` block JSON is the editable source document.
- Rendered HTML carries stable `adclip:block:<id>` markers.
- HTML patches target those markers; do not introduce coordinate-based editing.
- The native renderer must remain usable without Node.js or MJML.
- MJML may be added as optional import/export or compilation support, not a
  mandatory runtime dependency.
- Render table-based, mostly inline-styled responsive HTML with a plain-text
  alternative.
- Reject scripts, forms, iframes, embedded objects, active media, and
  `javascript:` URLs.
- Marketing exports include visible unsubscribe treatment, postal-address
  metadata, `List-Unsubscribe`, and `List-Unsubscribe-Post`.
- Sender authentication, recipient-specific unsubscribe substitution, consent,
  suppression lists, and delivery belong to future sending adapters.
- Sending adapters consume exported content; they do not own campaign copy or
  design state.
- Rendering, linting, and patching must remain local and deterministic.
- Email sequence generation uses the same text-provider registry and runtime
  policy as ad copy.

## Evaluation policy

`adclip bakeoff` is dry-run by default. Paid execution requires `--execute` and
normal live-API authorization. The harness records:

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

Keep fixtures stable enough for longitudinal comparison. Add a fixture only
when it captures a materially different marketing failure mode.

## Runtime and billing policy

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

Configuration:

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

Provider-specific text configuration includes:

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

## Built-in providers

Text:

1. `claude-cli` — subscription-authenticated compatibility default.
2. `sampling` — sampling-capable MCP host.
3. `anthropic` — direct opt-in Anthropic API.
4. `openai-compatible` — local or hosted `/v1/chat/completions` endpoint.
5. `command` — local executable over stdin/stdout without a shell.
6. `fake` — deterministic test provider.

Media:

- fal image: GPT Image 2, Nano Banana, FLUX.2, legacy aliases, raw endpoints
- direct OpenAI image: standard Images API
- fal video: Kling, Veo, Seedance, Wan 2.7, Wan 2.6 legacy, raw endpoints
- fake image/video: deterministic tests

Reference-image editing, vector generation, multi-reference video,
image-animation, and footage-edit routes are cataloged but intentionally
non-executable until their input contracts and adapters exist.

Legacy `LLM*` names and `llm_*` arguments remain compatibility aliases.

## Vendored declip slice

`src/adclip/_video_backend.py` supplies legacy fal aliases and loudness logic.
It is a compatibility source, not the primary routing policy. Do not add
`declip` as a runtime dependency.

## Testing requirements

Use fake providers and mocked HTTP. Required media/provider coverage includes:

- provider/model independence and compatibility aliases;
- task-route recommendation and explicit overrides;
- unrelated model overrides not inheriting route-family options;
- non-executable route rejection;
- GPT Image, Nano Banana, FLUX, Kling, Veo, Seedance, Wan 2.7, and legacy Wan
  2.6 request schemas;
- direct OpenAI image handling;
- offline/air-gapped provider policy;
- unused modalities not being resolved;
- status reporting invalid configured routes without crashing;
- run-level route/provider/model provenance;
- dry-run bake-off making no provider call;
- CLI importing no module under `adclip.mcp`.

Required email coverage includes:

- marketing render includes HTML, text, footer, and one-click headers;
- generated block IDs are stable and unique;
- structured and rendered-HTML patches target the same block IDs;
- unsafe raw HTML and `javascript:` URLs are rejected;
- lint detects missing image alternatives, links, unsubscribe treatment, and
  blocked active content;
- generated cadence comes from the brief rather than model-invented values;
- campaign export writes message JSON, HTML, text, headers, lint, and manifest;
- email generation uses a fake text provider in tests;
- no send provider or network call is required.

Do not require a live model server, paid API, or email sending account in the
unit suite.

## Next milestone

S1 remains SQLite persistence, content-addressed artifacts, stable IDs/Manifest
v2, and durable resumable jobs. Route selection, email campaign/message state,
endpoint class, prompt version, parameters, cost, latency, retries, and artifact
hashes must become authoritative per-asset provenance.
