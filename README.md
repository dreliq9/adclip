# adclip

Ad creative generation — copy and static images — from a single JSON brief.
Runs as an MCP server (zero-config under Claude Code) or as a CLI.

**Keyless by default.** adclip shells out to the `claude` CLI for LLM calls
using your subscription auth, so no `ANTHROPIC_API_KEY` is needed. Paid
third-party APIs (Anthropic direct, fal.ai) are gated behind an explicit
opt-in (`ADCLIP_ALLOW_LIVE_APIS=1`) so a key in your environment doesn't
silently bill you.

## Install

```bash
pipx install adclip
```

For the optional direct-Anthropic-API provider:

```bash
pipx install "adclip[anthropic]"
```

Requires Python 3.11+ and the [claude CLI](https://docs.claude.com/claude-code)
on `$PATH` (for the default keyless LLM path).

### From source (for contributors)

```bash
git clone https://github.com/dreliq9/adclip.git
cd adclip
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Two usage paths

### 1. MCP server (recommended under Claude Code)

Add to your project's `.mcp.json` (or `~/.claude.json`):

```json
{
  "mcpServers": {
    "adclip": {
      "command": "adclip-mcp"
    }
  }
}
```

Then ask Claude: *"Generate ad variants for examples/taichi_brief.json"*

Tools exposed:

**Brief + inspection**
- `adclip_brief_validate` — schema check
- `adclip_estimate_cost` — LLM + fal cost estimate
- `adclip_list_formats` — format catalog
- `adclip_policy_check` — policy dry-run on arbitrary copy
- `adclip_campaign_status` — manifest, variants, costs, missing-file audit for a campaign dir

**Generation**
- `adclip_generate_copy` — copy pool only (preview/iterate before spending on images)
- `adclip_generate_visuals` — given a list of winner copies, produce images + composites
- `adclip_generate_variants` — full pipeline (copy → policy → image → compose → render)

**Iteration on an existing campaign**
- `adclip_render_variant` — re-composite one variant (cheap; no LLM, no fal)
- `adclip_regenerate` — redo one variant's copy, visual, or both
- `adclip_score_variants` — re-rank variants against (possibly edited) brief; heuristic or LLM judge
- `adclip_export_dco` — emit Meta DCO modular components (deduped headlines/bodies/ctas + per-aspect images)

### 2. CLI

```bash
adclip formats                              # list format specs
adclip estimate examples/taichi_brief.json  # cost preview
adclip copy examples/taichi_brief.json      # copy only (no images)
adclip run  examples/taichi_brief.json --image fake  # full pipeline, stub images
```

The CLI also uses `claude-cli` by default — no key setup needed.

## Brief schema

See `src/adclip/schema.py` for the full `AdBrief`. Minimal example:

```json
{
  "product": "Taichi crypto trading bot",
  "value_prop": "Paper-trade our signals before risking real cash.",
  "audience": "Skeptical retail crypto traders.",
  "angles": ["credibility", "curiosity"],
  "tone": "confident, dry, no hype",
  "cta": "Start paper trading",
  "formats": ["meta_feed_4x5", "google_rsa"],
  "variants": 2,
  "pool_size": 3,
  "policy_profile": "crypto",
  "must_avoid": ["guaranteed returns"],
  "use_judge": true,
  "heal_violations": 2,
  "output_dir": "/tmp/adclip_out"
}
```

## Formats

| Name                         | Aspect  | Size        | Kind   |
|------------------------------|---------|-------------|--------|
| `meta_feed_1x1`              | 1:1     | 1080x1080   | static |
| `meta_feed_4x5`              | 4:5     | 1080x1350   | static |
| `google_display_square`      | 1:1     | 1200x1200   | static |
| `google_display_landscape`   | 1.91:1  | 1200x628    | static |
| `linkedin_single`            | 1.91:1  | 1200x627    | static |
| `x_promoted`                 | 16:9    | 1200x675    | static |
| `google_rsa`                 | text    | —           | text   |
| `stories_reels_9x16`         | 9:16    | 1080x1920   | video¹ |
| `tiktok_9x16`                | 9:16    | 1080x1920   | video¹ |
| `youtube_shorts_9x16`        | 9:16    | 1080x1920   | video¹ |

¹ Video formats are declared in the schema but the pipeline does not yet
produce video assets (v0.1 is static + text only). They land with a
`"video formats not yet implemented in pipeline"` note in the manifest.

## LLM provider modes

| Mode            | Key?    | Where it runs                       |
|-----------------|---------|-------------------------------------|
| `default` / `claude-cli` | none | Subprocess to the `claude` CLI; uses your subscription auth. |
| `sampling`      | none    | MCP sampling — asks the calling MCP client to run the LLM. Only works under clients that implement sampling (Claude Code does not today). |
| `anthropic`     | `adclip[anthropic]` extra + key + `ADCLIP_ALLOW_LIVE_APIS=1` | Direct Anthropic API. ~3x faster per call. |
| `fake`          | none    | Deterministic scripted responses for tests. |

## Live-API opt-in

`ADCLIP_ALLOW_LIVE_APIS=1` must be set to use any paid third-party API.
This applies to `anthropic` and `fal.ai` (image + video). If a key happens
to be in your env but the gate is closed, the provider refuses with a
clear error instead of billing you.

For local dev and most MCP work you should never need to set this — the
default paths are all keyless.

## Self-review loops

- **Judge** (`use_judge: true`): after policy-filtering, an LLM scores each
  survivor on brand fit, angle fit, and copy quality; top-N by blended
  score wins. `judge_score`, `judge_rationale`, `judge_flags` land in
  the manifest.
- **Heal** (`heal_violations: N`): policy-violating candidates are sent
  back to the LLM with the specific violations and asked to rewrite.
  Successful heals gain a `heal_attempts` count and a `healed_from`
  snapshot of the original copy.
- **Semantic policy** (`use_semantic_policy: true`): an LLM second-pass
  flags paraphrases that slip past the literal blocklist (e.g. "printing
  money" when `must_avoid` contains "guaranteed returns"). Feeds the
  same heal loop. Adds one LLM call per candidate — opt-in.

## Tests

```bash
.venv/bin/python -m pytest
```

## Status

**v0.1 (current):** static images + text ads, policy + heal + semantic
policy loops, full MCP tool surface (12 tools), CLI, claude-cli /
sampling / anthropic / fake LLM providers. Meta DCO modular-component
export via `adclip_export_dco`.

**Deferred:** video pipeline (`stories_reels_9x16`, `tiktok_9x16`,
`youtube_shorts_9x16` are declared but not produced), adversarial
critic — see `v0.x` plan notes in the repo.
