# Model and Provider Architecture

**Status:** Active contract  
**Date:** 2026-08-07

adclip treats a provider and a model as separate selections:

```text
workflow -> capability -> provider adapter -> model ID
```

Campaign, policy, scoring, and interface code must not branch on vendor or
model names. Provider adapters implement neutral capabilities and advertise
runtime requirements and model-override support.

## Configuration precedence

Text provider selection uses:

1. explicit CLI/MCP/application argument;
2. `ADCLIP_TEXT_PROVIDER`;
3. compatibility default `claude-cli`.

Text model selection uses:

1. explicit `--model`, `--text-model`, or MCP model argument;
2. provider-specific model environment variable;
3. `ADCLIP_TEXT_MODEL`;
4. provider default.

Media follows the same separation:

```text
ADCLIP_IMAGE_PROVIDER
ADCLIP_IMAGE_MODEL
ADCLIP_VIDEO_PROVIDER
ADCLIP_VIDEO_MODEL
```

The same selection contract now applies to full generation, visual-only
generation, variant regeneration, and LLM-based variant judging.

## Built-in text adapters

| Provider | Model selection | Runtime |
| --- | --- | --- |
| `claude-cli` | `ADCLIP_CLAUDE_MODEL` or explicit model | External network through the Claude CLI |
| `sampling` | Host-selected | Requires a sampling-capable MCP session |
| `anthropic` | `ADCLIP_ANTHROPIC_MODEL` or explicit model | External, potentially paid |
| `openai-compatible` | Required explicit/configured model | Local loopback or external compatible endpoint |
| `command` | `ADCLIP_COMMAND_TEXT_MODEL` or explicit model | Local subprocess; allowed air-gapped |
| `fake` | Any identity accepted for deterministic tests | In-process |

### OpenAI-compatible HTTP

The `openai-compatible` adapter uses the HTTP contract directly and does not
require a vendor SDK. Configure it with:

```bash
ADCLIP_TEXT_PROVIDER=openai-compatible
ADCLIP_TEXT_MODEL=qwen2.5:14b
ADCLIP_OPENAI_BASE_URL=http://127.0.0.1:11434/v1
ADCLIP_RUNTIME_MODE=offline
```

The base URL may point to any server or gateway implementing
`/v1/chat/completions`. `ADCLIP_OPENAI_API_KEY` is optional for loopback
servers. A non-loopback endpoint is treated as external and potentially paid,
so it requires normal runtime authorization.

### Generic local command

The `command` adapter supports local model CLIs that do not expose HTTP:

```bash
export ADCLIP_TEXT_PROVIDER=command
export ADCLIP_COMMAND_TEXT_COMMAND='my-model-cli --model {model} --json'
export ADCLIP_COMMAND_TEXT_MODEL=my-local-model
export ADCLIP_RUNTIME_MODE=air_gapped
```

The executable receives the prompt on stdin and must write the raw response to
stdout. adclip never invokes a shell. Individual command arguments may contain
`{model}` and `{n}` placeholders; the same values are available in
`ADCLIP_MODEL` and `ADCLIP_CANDIDATE_COUNT`.

## CLI examples

```bash
# Local OpenAI-compatible text generation
adclip copy brief.json \
  --provider openai-compatible \
  --model qwen2.5:14b

# Choose each modality independently
adclip run brief.json \
  --text-provider openai-compatible \
  --text-model qwen2.5:14b \
  --image-provider fal \
  --image-model imagen-3 \
  --video-provider fal \
  --video-model veo-3.1
```

Compatibility flags remain available:

```text
--llm          -> --text-provider
--llm-model    -> --text-model
--image        -> --image-provider
--video        -> --video-provider
```

## Media model IDs

The fal image adapter accepts both friendly aliases and raw endpoint IDs:

```text
flux-dev
imagen-3
fal-ai/vendor/custom-image-model
```

The video adapter already accepts aliases and raw endpoints through its model
catalog resolver. Unknown-model pricing remains conservative until the model
cost registry is introduced.

## Runtime policy

Loopback inference is not equivalent to external network access. Local HTTP
model servers are allowed in `offline` and `air_gapped` modes. External
endpoints are refused in those modes. In `restricted_network`, external
providers require an allowlist entry.

Local command providers require no network access. Provider adapters whose
endpoints are configurable must re-evaluate runtime requirements after reading
their endpoint. Static registry metadata alone is not sufficient.

## Extension contract

A new text adapter should:

1. implement `TextGenerationProvider.generate(prompt, n)`;
2. register a lazy `TextProviderSpec` factory;
3. declare capabilities and runtime requirements;
4. accept a model through `TextProviderContext` when model override is
   supported;
5. avoid imports from CLI, MCP, or application modules;
6. return text only—the workflow owns prompt and schema semantics.

Future structured-generation work may expand the neutral contract, but legacy
`generate(prompt, n)` support must remain through an adapter until a versioned
migration exists.

Image and video adapters currently use callable `MediaProviderBinding` objects
with provider/model metadata. They should migrate to the same registry pattern
when a second production provider is added; campaign code must not be changed
to add that provider.

## Provenance requirement

Every durable generation record must eventually contain:

```text
provider
model
endpoint class (loopback/external/host session)
prompt version
seed
generation parameters
cost estimate and actual cost
artifact hash
```

The current application and model-using MCP workflows return selected
provider/model identities. Manifest v2 and durable jobs will make this
provenance authoritative in milestone S1.
