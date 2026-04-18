# CLAUDE.md — adclip project context

## No API key, by construction

adclip never requires `ANTHROPIC_API_KEY`. Any runtime error mentioning a
missing key means the wrong provider got instantiated. **Do not add the key
as a workaround.** Do not write code that reads it. Do not rewrite the
LLM layer.

## The three LLM provider paths

1. **Claude CLI subprocess** (`ClaudeCliProvider`) — shells out to
   `claude -p` using the user's subscription auth. No key. This is the
   default for both the MCP tools and the CLI. Claude Code's MCP client
   does not currently implement sampling, so the MCP tools route
   `"default"` here for reliability.

2. **MCP sampling** (`SamplingLLMProvider`) — opt-in via
   `llm_provider="sampling"`. The host MCP client runs LLM completions
   on adclip's behalf. No key. Only works under clients that implement
   sampling.

3. **Direct Anthropic API** (`AnthropicProvider`) — opt-in only, for
   users with a key who want ~3x faster per-call latency. Never a
   default. Also gated behind `ADCLIP_ALLOW_LIVE_APIS=1` so a stray
   key in the environment doesn't silently bill you.

## Testing

Use `--llm fake` / `provider_name="fake"` in tests. `FakeLLMProvider` is
deterministic and sync-safe via `asyncio.run`.

## If you hit an LLM error

- "ANTHROPIC_API_KEY not set": you instantiated `AnthropicProvider`
  somewhere. Replace with `default_provider()` or `ClaudeCliProvider()`.
- "sampling provider requires an MCP session": you're outside an MCP
  session (e.g., CLI context). Use `ClaudeCliProvider` or pass `--llm
  claude-cli` explicitly.
- "claude CLI failed": check `which claude` and that subscription auth
  is active (`claude -p "hello"` should return a response).

## Scope for contributors

- Static ads + text ads (v0.1)
- Self-review loops: judge + heal + semantic policy (v0.2)
- Keyless CLI via claude subprocess (v0.3)
- Full MCP tool surface: 12 tools — brief/cost/format, copy, policy,
  generate_copy, generate_visuals, generate_variants, render_variant,
  regenerate, score_variants, campaign_status, export_dco
- Video pipeline, adversarial critic: deferred (see v0.x plans)
