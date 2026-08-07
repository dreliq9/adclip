# CLAUDE.md — adclip project context

## Standalone product contract

adclip is a standalone, local-first marketing creative application. MCP is one
interface adapter; it is not the application architecture.

Read `docs/STANDALONE_ARCHITECTURE.md` before making architectural changes.
The following rules are binding:

- Core/domain/application modules must not import from `adclip.mcp`.
- CLI, MCP, and future HTTP/UI code are sibling adapters over
  `AdclipApplication`.
- New workflows belong in the application layer, not private MCP helpers.
- Provider implementations are selected through registries/capability
  interfaces rather than transport-specific conditionals.
- declip, FCP-MCP, youtube-mcp-v2, the Abductive Reasoning Kernel, and platform
  MCPs are optional enhancements. Baseline workflows may not require them.
- Existing CLI commands, MCP tool names, JSON briefs, and campaign-directory
  exports remain compatible while the persistent application is built.

Runtime modes are controlled by `ADCLIP_RUNTIME_MODE`:
`online`, `restricted_network`, `offline`, and `air_gapped`. Restricted mode
uses `ADCLIP_ALLOWED_NETWORK_PROVIDERS`. Paid providers still require
`ADCLIP_ALLOW_LIVE_APIS=1`.

## Vendored declip slice

`src/adclip/_video_backend.py` is a small (~350-line) vendored slice of
declip's `fetch_models.py` and `ops.loudnorm`. It is the **only** code adclip
needs from declip; the rest of declip's video-editor surface is out of scope
here. adclip is pipx-installable as a single package — do not add `declip` as a
runtime dependency.

When to sync `_video_backend.py` against declip:

- fal.ai redesigns its `/explore` page (breaks `_CARD_PATTERN`)
- New model families ship and we want hardcoded aliases beyond the live
  catalog (Kling/Wan/Veo/Sora successors)
- declip refines the loudnorm two-pass logic in a way we want

The earlier `render_schema.py` + `backends/ffmpeg.py` vendoring drifted because
those files were huge AND adclip did not actually use them. The current slice
is small, fully exercised, and easy to keep in sync.

## No API key, by construction

adclip never requires `ANTHROPIC_API_KEY`. Any runtime error mentioning a
missing key means the wrong provider got instantiated. **Do not add the key as
a workaround.** Do not rewrite the LLM layer to make a paid provider the
default.

## The three production LLM provider paths

1. **Claude CLI subprocess** (`ClaudeCliProvider`) — shells out to `claude -p`
   using the user's subscription auth. No API key. This is the default for both
   MCP tools and CLI. It is still a network-requiring provider and is refused
   in offline/air-gapped runtime modes.

2. **MCP sampling** (`SamplingLLMProvider`) — opt-in via
   `llm_provider="sampling"`. The host MCP client runs completions on adclip's
   behalf. No key. It requires a sampling-capable connected session.

3. **Direct Anthropic API** (`AnthropicProvider`) — opt-in only, for users with
   a key. Never a default. It is gated behind `ADCLIP_ALLOW_LIVE_APIS=1` so a
   stray key in the environment cannot silently bill the user.

`FakeLLMProvider` is the deterministic test path.

Provider names and requirements are registered in
`adclip.providers.registry`; do not recreate resolver branches in interface
modules.

## Testing

Use `--llm fake` / `provider_name="fake"` in tests. `FakeLLMProvider` is
deterministic and sync-safe via `asyncio.run`.

For interface work, verify that:

- application tests do not need MCP installed or running;
- CLI imports no module under `adclip.mcp`;
- MCP compatibility helpers preserve existing tool behavior;
- offline mode rejects network providers before invocation;
- fake providers continue to work in offline mode.

## If you hit an LLM error

- `Provider 'claude-cli' requires network access`: runtime mode is `offline` or
  `air_gapped`. Select a local provider when one is configured, use `fake` in
  tests, or switch runtime mode intentionally.
- `Provider 'anthropic' may incur paid API charges`: set
  `ADCLIP_ALLOW_LIVE_APIS=1` only when paid use is intended.
- `sampling provider requires an MCP session`: use `claude-cli` outside a
  sampling-capable MCP host.
- `ANTHROPIC_API_KEY not set`: direct Anthropic was selected. Use the default
  provider unless direct API usage is intentional.
- `claude CLI failed`: check `which claude` and active subscription auth.

## Current scope

- Static ads + text ads
- 9:16 video ads through the vendored video slice
- Self-review loops: judge + heal + semantic policy
- Keyless CLI through the Claude subprocess provider
- Full MCP tool surface: brief/cost/format, copy, policy, generation,
  iteration, scoring, status, and modular Meta export
- Transport-neutral `AdclipApplication`
- Centralized LLM provider registry and runtime policy

The next standalone milestones are SQLite persistence, content-addressed
artifacts, durable/resumable jobs, BrandKit/SourceLibrary, and `adclip serve`.
An adversarial critic remains deferred.
