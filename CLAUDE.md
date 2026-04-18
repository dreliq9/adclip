# CLAUDE.md — adclip project context

## No API key, by construction

adclip never requires `ANTHROPIC_API_KEY`. Any runtime error mentioning a
missing key means the wrong provider got instantiated. **Do not add the key
as a workaround.** Do not write code that reads it. Do not rewrite the
LLM layer.

## The three LLM provider paths

1. **MCP sampling** (`SamplingLLMProvider`) — when adclip runs as an MCP
   server under Claude Code. The host client runs LLM completions on
   adclip's behalf. No key. This is the default for MCP tools.

2. **Claude CLI subprocess** (`ClaudeCliProvider`) — when adclip runs via
   its CLI (`adclip run`, `adclip copy`). Shells out to `claude -p` using
   the user's subscription auth. No key. Default for the CLI.

3. **Direct Anthropic API** (`AnthropicProvider`) — opt-in only, for users
   with a key who want ~3x faster per-call latency. Never a default.

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

- Static ads + text ads only (v0.1)
- Self-review loops: judge + heal (v0.2)
- Keyless CLI via claude subprocess (v0.3)
- Video pipeline, modular DCO, adversarial critic: deferred (see v0.x plans)
