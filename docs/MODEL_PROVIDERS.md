# Model and Provider Architecture

**Status:** Active contract  
**Date:** 2026-08-07

adclip treats task, route, provider, model, and generation options as separate
concepts:

```text
workflow -> creative task -> route -> provider adapter -> model + options
```

Campaign, policy, scoring, and interface code must not branch on vendors.
Provider adapters implement neutral capabilities, declare runtime requirements,
and translate neutral requests into vendor-specific schemas. Route selection is
documented in `docs/MODEL_ROUTING.md`.

## Configuration precedence

Text provider:

1. explicit CLI/MCP/application argument;
2. `ADCLIP_TEXT_PROVIDER`;
3. compatibility default `claude-cli`.

Text model:

1. explicit `--model`, `--text-model`, or MCP argument;
2. provider-specific model environment variable;
3. `ADCLIP_TEXT_MODEL`;
4. provider default.

Media:

```text
ADCLIP_IMAGE_ROUTE
ADCLIP_IMAGE_PROVIDER
ADCLIP_IMAGE_MODEL
ADCLIP_VIDEO_ROUTE
ADCLIP_VIDEO_PROVIDER
ADCLIP_VIDEO_MODEL
```

Explicit provider/model values override a route primary. A model override from a
different family must not inherit options validated only for the original
route target.

## Text adapters

| Provider | Runtime |
| --- | --- |
| `claude-cli` | External through Claude CLI |
| `sampling` | Sampling-capable MCP host |
| `anthropic` | External, potentially paid |
| `openai-compatible` | Local loopback or external compatible HTTP |
| `command` | Local subprocess, air-gapped capable |
| `fake` | In-process testing |

OpenAI-compatible text:

```bash
ADCLIP_TEXT_PROVIDER=openai-compatible
ADCLIP_TEXT_MODEL=qwen2.5:14b
ADCLIP_OPENAI_BASE_URL=http://127.0.0.1:11434/v1
ADCLIP_RUNTIME_MODE=offline
```

Local command text:

```bash
ADCLIP_TEXT_PROVIDER=command
ADCLIP_COMMAND_TEXT_COMMAND='my-model-cli --model {model} --json'
ADCLIP_COMMAND_TEXT_MODEL=my-local-model
ADCLIP_RUNTIME_MODE=air_gapped
```

The command adapter sends the prompt through stdin, reads stdout, and never
invokes a shell.

## Image adapters

### fal

Supported current families include:

- GPT Image 2
- Nano Banana 2, Pro, and Lite
- FLUX.2 base, Pro, Flex, and Max
- legacy FLUX/Imagen aliases
- raw fal endpoint IDs

The adapter is schema-aware. GPT Image uses custom pixel dimensions and quality;
Nano Banana uses aspect ratio and resolution; FLUX uses pixel dimensions and
inference controls. Do not collapse these into one request dictionary.

### direct OpenAI

The direct adapter calls `/v1/images/generations`, supports GPT Image model IDs,
and handles base64 or URL responses. It uses the normal live-API gate and
`ADCLIP_OPENAI_IMAGE_API_KEY` or `OPENAI_API_KEY`.

### fake

The fake provider is deterministic and intended for tests.

## Video adapters

The fal adapter supports current aliases for:

- Kling O3 Standard and Kling 3 Standard
- Veo 3.1 and Veo 3.1 Fast
- Seedance 2 Standard, Fast, and reference endpoint
- Wan 2.7
- Wan 2.6 as a legacy compatibility path
- legacy aliases and raw endpoints

Each family has a distinct request builder. Supported duration, resolution,
aspect-ratio, audio, reference, and shot-control values are normalized before
submission. Wan 2.7 supports flexible 2–15 second output; legacy Wan 2.6 keeps
its narrower duration normalization.

The fake video provider remains deterministic. Runway, Recraft, local FLUX, and
other providers appear in the route catalog only where useful; they are not
advertised as executable until their adapters exist.

## Runtime policy

Loopback inference is not equivalent to external network access. Local HTTP
model servers are allowed in `offline` and `air_gapped` modes. External
endpoints are refused. Local command providers require no network access.
Potentially paid providers require `ADCLIP_ALLOW_LIVE_APIS=1`.

Provider status must remain inspectable even when an environment variable names
a cataloged but currently non-executable route. Configuration errors are data,
not a reason for `adclip status` to crash.

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

Routes expose ordered fallbacks, but adclip does not automatically run another
paid target after failure. A future retry policy must explicitly define:

```text
maximum additional cost
maximum attempts
eligible failure classes
approved fallback targets
whether partial results may be retained
```

## Provenance

Current manifests persist route/provider/model/options at run level. Durable
records must eventually contain:

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
