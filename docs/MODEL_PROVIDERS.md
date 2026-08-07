# Model and Provider Architecture

**Status:** Active contract  
**Date:** 2026-08-07

adclip treats task, route, provider, model, and generation options as separate
concepts:

```text
workflow -> creative task -> route -> provider adapter -> model + options
```

Campaign, policy, scoring, and interface code must not branch on model vendors.
Provider adapters implement neutral capabilities, advertise runtime
requirements, and translate neutral requests into vendor-specific schemas.
Route selection is documented separately in `docs/MODEL_ROUTING.md`.

## Configuration precedence

Text provider selection:

1. explicit CLI/MCP/application argument;
2. `ADCLIP_TEXT_PROVIDER`;
3. compatibility default `claude-cli`.

Text model selection:

1. explicit `--model`, `--text-model`, or MCP argument;
2. provider-specific model environment variable;
3. `ADCLIP_TEXT_MODEL`;
4. provider default.

Media selection:

```text
ADCLIP_IMAGE_ROUTE
ADCLIP_IMAGE_PROVIDER
ADCLIP_IMAGE_MODEL
ADCLIP_VIDEO_ROUTE
ADCLIP_VIDEO_PROVIDER
ADCLIP_VIDEO_MODEL
```

An explicit provider/model overrides the selected route primary. Route options
remain unless the explicit model is unrelated to the route target, in which
case only explicitly supplied options should be assumed.

## Built-in text adapters

| Provider | Model selection | Runtime |
| --- | --- | --- |
| `claude-cli` | `ADCLIP_CLAUDE_MODEL` or explicit model | External through Claude CLI |
| `sampling` | Host-selected | Sampling-capable MCP session |
| `anthropic` | `ADCLIP_ANTHROPIC_MODEL` or explicit model | External, potentially paid |
| `openai-compatible` | Required explicit/configured model | Local loopback or external compatible HTTP |
| `command` | `ADCLIP_COMMAND_TEXT_MODEL` or explicit model | Local subprocess, air-gapped capable |
| `fake` | Arbitrary deterministic identity | In-process |

### OpenAI-compatible text

```bash
ADCLIP_TEXT_PROVIDER=openai-compatible
ADCLIP_TEXT_MODEL=qwen2.5:14b
ADCLIP_OPENAI_BASE_URL=http://127.0.0.1:11434/v1
ADCLIP_RUNTIME_MODE=offline
```

The adapter speaks `/v1/chat/completions` directly and has no OpenAI SDK
dependency. A non-loopback endpoint is treated as external and potentially paid.

### Local command text

```bash
ADCLIP_TEXT_PROVIDER=command
ADCLIP_COMMAND_TEXT_COMMAND='my-model-cli --model {model} --json'
ADCLIP_COMMAND_TEXT_MODEL=my-local-model
ADCLIP_RUNTIME_MODE=air_gapped
```

The prompt is sent over stdin and the raw response is read from stdout. adclip
never invokes a shell.

## Image adapters

### fal

The fal image adapter supports current aliases for:

- GPT Image 2
- Nano Banana 2, Pro, and Lite
- FLUX.2 base, Pro, Flex, and Max
- legacy FLUX/Imagen aliases
- raw fal endpoint IDs

The adapter is schema-aware. GPT Image uses custom pixel dimensions and quality;
Nano Banana uses aspect ratio and resolution; FLUX uses pixel dimensions and
inference controls. Do not collapse these into one request dictionary.

### direct OpenAI

The direct OpenAI adapter calls `/v1/images/generations`, accepts GPT Image model
IDs, and handles base64 or URL results. It uses the normal live-API gate and
`ADCLIP_OPENAI_IMAGE_API_KEY` or `OPENAI_API_KEY`.

### fake

The fake image provider is deterministic and intended for tests.

## Video adapters

The fal video adapter supports current aliases for:

- Kling O3 Standard and Kling 3 Standard
- Veo 3.1 and Veo 3.1 Fast
- Seedance 2 Standard, Fast, and reference endpoint
- Wan 2.6
- legacy aliases and raw endpoints

Each family has a distinct request builder. Supported durations, resolution,
aspect ratios, audio flags, reference fields, and shot controls are normalized
before submission.

The fake video provider remains deterministic for tests. Runway, Recraft, local
FLUX, and other providers are represented in the route catalog where useful,
but are not advertised as executable until their adapters exist.

## Runtime policy

Loopback inference is not equivalent to external network access. Local HTTP
model servers are allowed in `offline` and `air_gapped` modes. External
endpoints are refused. Local command providers require no network access.
Potentially paid providers require `ADCLIP_ALLOW_LIVE_APIS=1`.

## Adapter extension contract

A new adapter must:

1. implement the neutral capability contract;
2. register lazily;
3. declare runtime and billing requirements;
4. accept model/options independently when supported;
5. isolate vendor schema translation inside the adapter;
6. avoid imports from CLI, MCP, campaign, policy, or scoring modules;
7. return provider/model/cost information suitable for provenance;
8. provide deterministic mocked tests.

Adding a provider must not require campaign-level conditionals.

## Fallback policy

Routes expose ordered fallback targets, but adclip does not automatically run a
fallback after a failed paid call. The application may later support an
explicitly authorized retry budget, but fallback execution must remain visible,
auditable, and bounded.

## Provenance

Current campaign manifests persist route/provider/model/options at run level.
Durable generation records must eventually contain:

```text
route
provider
model
endpoint class
prompt and prompt version
seed
generation parameters
estimated and actual cost
latency
failure/retry history
artifact hash
```

Manifest v2 and durable jobs will make this authoritative per asset in S1.
