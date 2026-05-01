# CLAUDE.md — adclip project context

## Vendored declip slice

`src/adclip/_video_backend.py` is a small (~350-line) vendored slice of
declip's `fetch_models.py` and `ops.loudnorm`. It is the **only** code
adclip needs from declip; the rest of declip's video-editor surface is
out of scope here. adclip is pipx-installable as a single package — do
not add `declip` as a runtime dependency.

When to sync `_video_backend.py` against declip:

- fal.ai redesigns its `/explore` page (breaks `_CARD_PATTERN`)
- New model families ship and we want hardcoded aliases beyond the live
  catalog (Kling/Wan/Veo/Sora successors)
- declip refines the loudnorm two-pass logic in a way we want

The earlier `render_schema.py` + `backends/ffmpeg.py` vendoring drifted
because those files were huge AND adclip didn't actually use them. The
current slice is small, fully exercised, and easy to keep in sync.

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
