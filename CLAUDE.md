# CLAUDE.md — adclip project context

## Standalone product contract

adclip is a standalone, local-first, model-agnostic marketing creative
application. MCP is one interface adapter; it is not the application
architecture.

Read `docs/STANDALONE_ARCHITECTURE.md` and `docs/MODEL_PROVIDERS.md` before
making architectural changes. These rules are binding:

- Core/domain/application modules must not import from `adclip.mcp`.
- CLI, MCP, and future HTTP/UI code are sibling adapters over
  `AdclipApplication`.
- New workflows belong in the application layer, not private MCP helpers.
- Workflow code selects capabilities; it must not branch on vendor or model
  names.
- Provider and model are separate values. A provider adapter receives the
  selected model through its construction context.
- Provider implementations are selected through registries/capability
  interfaces rather than transport-specific conditionals.
- declip, FCP-MCP, youtube-mcp-v2, the Abductive Reasoning Kernel, and platform
  MCPs are optional enhancements. Baseline workflows may not require them.
- Existing CLI commands, compatibility flags, MCP tool names, JSON briefs, and
  campaign-directory exports remain compatible during migration.

## Runtime policy

Runtime modes are controlled by `ADCLIP_RUNTIME_MODE`:

```text
online
restricted_network
offline
air_gapped
```

`ADCLIP_ALLOWED_NETWORK_PROVIDERS` controls external access in restricted mode.
Paid providers still require `ADCLIP_ALLOW_LIVE_APIS=1`.

Loopback HTTP inference is allowed in offline and air-gapped modes. External
HTTP endpoints are not. Endpoint-configurable adapters must re-check runtime
requirements after reading their configured URL.

## Provider and model configuration

Primary configuration:

```text
ADCLIP_TEXT_PROVIDER
ADCLIP_TEXT_MODEL
ADCLIP_IMAGE_PROVIDER
ADCLIP_IMAGE_MODEL
ADCLIP_VIDEO_PROVIDER
ADCLIP_VIDEO_MODEL
```

Provider-specific text model variables currently include:

```text
ADCLIP_CLAUDE_MODEL
ADCLIP_ANTHROPIC_MODEL
ADCLIP_OPENAI_MODEL
```

The generic OpenAI-compatible adapter uses:

```text
ADCLIP_OPENAI_BASE_URL
ADCLIP_OPENAI_API_KEY       # optional for local endpoints
ADCLIP_OPENAI_TIMEOUT
```

Do not add a vendor SDK when the standard compatible HTTP contract is
sufficient. Do not import vendor code into application, campaign, policy,
scoring, CLI, or MCP modules.

## Built-in text paths

1. **Claude CLI** (`claude-cli`) — subscription-authenticated subprocess.
   Compatibility default; still an external-network provider.
2. **MCP sampling** (`sampling`) — delegates to a sampling-capable host. The
   host controls model selection.
3. **Direct Anthropic** (`anthropic`) — opt-in paid API adapter.
4. **OpenAI-compatible** (`openai-compatible`) — generic local or hosted
   `/v1/chat/completions` endpoint; no SDK dependency.
5. **Fake** (`fake`) — deterministic in-process test provider.

The legacy names `LLMProviderRegistry`, `LLMProviderSpec`,
`default_llm_registry`, `resolve_llm_provider`, and `llm_*` arguments remain as
compatibility aliases. New code should use text-provider terminology.

## Vendored declip slice

`src/adclip/_video_backend.py` is a small vendored slice of declip's model
catalog and loudness logic. It is the only code adclip needs from declip. Do
not add `declip` as a runtime dependency.

Sync the slice when:

- fal.ai changes the catalog shape;
- useful new video aliases need coverage;
- relevant loudness logic improves in declip.

## Billing safety

adclip does not require a paid API on its default path. Do not add keys as a
workaround for provider-selection errors. A potentially paid provider must be
explicitly selected and authorized.

A non-loopback OpenAI-compatible endpoint is conservatively treated as
potentially paid even when no key is configured. This may be relaxed later by
an explicit provider configuration record, not by guessing from a URL.

## Testing

Use `fake` providers for deterministic workflow tests. Provider tests should
cover:

- provider and model selected independently;
- explicit model overriding provider defaults;
- compatibility aliases continuing to resolve;
- local compatible HTTP allowed offline;
- external compatible HTTP blocked offline;
- external potentially paid endpoints requiring authorization;
- CLI importing no module under `adclip.mcp`;
- MCP forwarding provider and model without vendor conditionals;
- image and video model overrides reaching their adapters.

Use mocked HTTP for the OpenAI-compatible adapter. Do not require a running
model server in the unit suite.

## Common errors

- `requires network access outside loopback`: an external provider was selected
  in offline or air-gapped mode.
- `may incur paid API charges`: set `ADCLIP_ALLOW_LIVE_APIS=1` only when use is
  intentional.
- `requires an MCP session`: sampling was selected outside an appropriate host.
- `requires an explicit model`: pass `--model`/`--text-model` or configure
  `ADCLIP_TEXT_MODEL`.
- `requires ADCLIP_OPENAI_BASE_URL`: configure the compatible HTTP API base.
- `claude CLI failed`: check the executable and subscription auth.

## Current scope

- Static, text, and 9:16 video creative
- Policy, healing, semantic review, and judging
- Transport-neutral `AdclipApplication`
- Provider-neutral text contract and registry
- Independent text/image/video model selection
- Local or hosted OpenAI-compatible text inference
- Explicit runtime and paid-provider policy
- Standalone CLI and full MCP surface

The next standalone milestone remains S1: SQLite persistence,
content-addressed artifacts, stable IDs/Manifest v2, and durable resumable
jobs. Provider/model identity must become persistent provenance in that work.
