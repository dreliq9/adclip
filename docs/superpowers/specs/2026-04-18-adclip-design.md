# adclip — Design Spec

**Date:** 2026-04-18
**Status:** Approved design, pending implementation plan
**Location:** `~/Desktop/adclip/` (peer to `~/Desktop/declip/`)

## Purpose

`adclip` is an MCP server for generating advertising creative. It turns a structured `AdBrief` into finished ad assets (copy, images, video) sized and formatted for specific ad platforms (Meta, Google, TikTok, LinkedIn, X, YouTube).

It sits above `declip` conceptually but is a standalone peer project. It clones declip's stable rendering primitives (ffmpeg ops, fal.ai video gen, TTS, overlays, platform export) and adds an ad-creative layer on top: brief schema, LLM copywriting, static image generation, variant strategy, and policy checks.

## Why a fork, not a library dependency

Declip improvements won't flow into adclip automatically — porting is manual. Accepted tradeoff: rendering primitives (fade, crop, concat, loudness) are stable; the ad-creative layer is where innovation will happen. Decoupling release cycles is worth more than diff-free sync.

## Architecture

```
~/Desktop/adclip/
├── pyproject.toml            # peer to declip, own venv, declip-compatible deps
├── src/adclip/
│   ├── schema.py             # AdBrief, Variant, Campaign, AdFormat (NEW)
│   ├── copy.py               # LLM copywriting + char-limit enforcement (NEW)
│   ├── image_gen.py          # fal.ai Flux / Imagen for static images (NEW)
│   ├── video_gen.py          # CLONED from declip/generate.py (fal video)
│   ├── compose.py            # AdBrief → render plan JSON (NEW)
│   ├── render.py             # render pipeline, wraps ops.py (NEW-ish)
│   ├── ops.py                # CLONED from declip/ops.py (shared ffmpeg)
│   ├── probe.py              # CLONED from declip/probe.py
│   ├── backends/ffmpeg.py    # CLONED from declip/backends/ffmpeg.py
│   ├── platform.py           # CLONED from declip platform_export
│   ├── overlays.py           # CLONED text/image overlay ops
│   ├── tts.py                # CLONED declip TTS + voice library
│   ├── captions.py           # CLONED auto-caption / subtitle burn
│   ├── audio.py              # CLONED loudness normalization, audio mix
│   ├── policy.py             # Ad policy checks per platform/vertical (NEW)
│   ├── scoring.py            # Score candidates against brief (NEW)
│   ├── cost.py               # Cost estimator for fal/LLM spend (NEW)
│   ├── cli.py                # `adclip` command
│   └── mcp/
│       ├── server.py         # FastMCP server entrypoint
│       ├── brief_tools.py    # validate, cost, formats
│       ├── copy_tools.py     # generate copy, policy check
│       ├── visual_tools.py   # generate images/video
│       ├── pipeline_tools.py # full generate, regenerate, export
│       └── campaign_tools.py # manage campaign directories
└── tests/
```

**Cloned from declip (lift-and-shift):** `generate.py` → `video_gen.py`, `ops.py`, `probe.py`, `backends/ffmpeg.py`, `platform_export` logic, TTS + voice library, text/image overlays, auto-caption + subtitle burn, loudness + audio mix, crop/resize, color grade, fades/transitions.

**Net new in adclip:** `schema.py`, `copy.py`, `image_gen.py`, `compose.py`, `policy.py`, `scoring.py`, `cost.py`, the MCP tool layer, ad-specific CLI commands.

## AdBrief schema — the API boundary

```python
class AdBrief(BaseModel):
    # Product / service
    product: str                         # "Taichi crypto trading bot"
    value_prop: str                      # "Paper-trade signals before risking cash"
    audience: str                        # "Retail crypto traders, skeptical of hype"

    # Creative direction — angles is a LIST (industry best practice: test multiple
    # angles against the same offer)
    angles: list[str]                    # e.g. ["credibility", "curiosity", "social_proof"]
    tone: str                            # "confident, dry, no hype"
    cta: str                             # "Start paper trading"

    # Format and variant strategy
    formats: list[AdFormat]              # ["meta_feed_4x5", "stories_reels_9x16", "google_rsa"]
    variants: int = 5                    # final variants per format
    pool_size: int = 15                  # generate N candidates, filter to `variants`
    variant_strategy: Literal[
        "angles",                        # vary angle, fix everything else (default)
        "hooks",                         # vary opening hook, fix angle
        "visuals",                       # vary image/framing, fix copy
        "modular_components",            # emit raw components for Meta DCO
    ] = "angles"

    # Brand assets
    logo_path: str | None = None
    brand_colors: list[str] = []         # hex
    product_screenshots: list[str] = []
    font_family: str | None = None

    # Constraints
    must_include: list[str] = []         # ["paper trading", "free tier"]
    must_avoid: list[str] = []           # ["guaranteed returns", "financial advice"]
    policy_profile: Literal[
        "default", "crypto", "health", "alcohol", "financial_services"
    ] = "default"

    # Output
    output_dir: str                      # campaign folder
    budget_usd: float | None = None      # caps fal+LLM spend; abort if exceeded
```

### AdFormat catalog

Each format carries its own spec and is enforced automatically. Char limits are from Meta/Google/TikTok published guidelines as of April 2026.

| Format                   | Aspect | Dimensions       | Headline chars | Body chars | Notes                                 |
|--------------------------|--------|------------------|----------------|------------|---------------------------------------|
| `meta_feed_1x1`          | 1:1    | 1080×1080        | 40 (27 rec.)   | 125        | Static or video                       |
| `meta_feed_4x5`          | 4:5    | 1080×1350        | 40             | 125        | Recommended for feed impact           |
| `stories_reels_9x16`     | 9:16   | 1080×1920        | 10 (overlay)   | 125        | **Unified March 2026**: FB/IG stories + FB/IG reels single safe zone |
| `google_rsa`             | text   | n/a              | 30             | 90         | Up to 15 headlines, up to 4 descriptions; min 3/2 |
| `google_display_square`  | 1:1    | 1200×1200        | 30             | 90         | Short headline 30, long 90            |
| `google_display_landscape`| 1.91:1| 1200×628         | 30             | 90         |                                       |
| `tiktok_9x16`            | 9:16   | 1080×1920        | 100 (caption)  | n/a        | 5-60s video, captions burned          |
| `youtube_shorts_9x16`    | 9:16   | 1080×1920        | 100 (title)    | n/a        | ≤60s                                  |
| `linkedin_single`        | 1.91:1 | 1200×627         | 70             | 600        | Intro 600, headline 70                |
| `x_promoted`             | 16:9   | 1200×675         | 280            | n/a        | Post-style                            |

**Removed from scope:** the old Meta "20% text rule" — Meta removed enforcement in 2020-2021. `policy.py` tracks text density as a **soft warning only**.

## Generation pipeline

```
AdBrief
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ 1. brief.validate(brief)                                │
│    → format specs, policy profile loaded                │
│    → cost.estimate() → warn/abort if > budget_usd       │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ 2. copy.generate_pool(brief, pool_size)                 │
│    → LLM call(s), one per (format × angle)              │
│    → returns pool_size candidates with char-limit-       │
│      compliant headlines, bodies, CTAs                  │
│    → policy.check(candidate) → drop violations          │
│    → scoring.rank(candidates, brief) → top `variants`   │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ 3. visual.generate(brief, variant)                      │
│    → static formats: fal Flux / Imagen → PNG            │
│    → video formats: fal Kling / Wan / Veo → MP4         │
│    → uses brand_colors, logo, product_screenshots       │
│    → policy.visual_check (logos, trademarks, etc.)      │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ 4. compose.build_project(variant)                       │
│    → assembles render plan (declip-style JSON)          │
│    → overlays: headline, CTA, logo                      │
│    → video: TTS voiceover + burned captions             │
│    → loudness normalize (LUFS per platform)             │
└─────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────┐
│ 5. render.run(project)                                  │
│    → ffmpeg pipeline via cloned ops.py                  │
│    → exports correct aspect ratio per format            │
│    → outputs to variant dir                             │
└─────────────────────────────────────────────────────────┘
```

### Modular / DCO output mode

When `variant_strategy = "modular_components"`, step 4 emits raw components instead of pre-assembled ads:

```
campaign/
  dco_components/
    headlines.json       # 5 headlines, char-compliant
    bodies.json          # 5 body texts
    ctas.json            # 3 CTAs
    images/              # 5 images, each at required aspect ratios
      img_01_1x1.png
      img_01_4x5.png
      img_01_9x16.png
      img_02_1x1.png
      ...
```

Meta DCO ingests these and mixes server-side. Industry data: 32% higher CTR, 56% lower CPC vs pre-assembled.

### Output directory layout (standard modes)

```
<output_dir>/
  brief.json                          # original input
  manifest.json                       # index, costs, timestamps, scores
  variants/
    v01/
      copy.json                       # headline, body, CTA, policy report, score
      visual_raw.png | .mp4           # generator output, pre-composition
      meta_feed_4x5.png               # final per-format renders
      meta_feed_1x1.png
      stories_reels_9x16.mp4
      google_rsa.json                 # text-only ad components
    v02/ ...
  pool_rejected/                      # candidates dropped by policy or scoring
    candidate_07.json
```

Each variant is self-contained. Re-render one without redoing all. Easy to A/B test.

## MCP tools

| Tool                          | Purpose                                                |
|-------------------------------|--------------------------------------------------------|
| `adclip_brief_validate`       | Schema check + format compatibility                    |
| `adclip_estimate_cost`        | Pre-run $ estimate (LLM tokens + fal image/video)      |
| `adclip_list_formats`         | Enumerate supported formats with their specs           |
| `adclip_generate_copy`        | Copy-only pipeline (cheap, iteration)                  |
| `adclip_generate_visuals`     | Visual-only (reuses existing copy)                     |
| `adclip_generate_variants`    | Full pipeline — copy + visual + compose + render       |
| `adclip_regenerate`           | Redo one variant (copy, visual, or both)               |
| `adclip_policy_check`         | Dry-run policy against existing copy                   |
| `adclip_export_dco`           | Produce modular DCO components from existing campaign  |
| `adclip_score_variants`       | Re-rank existing variants (useful after brief edits)   |
| `adclip_render_variant`       | Render a single variant to a specific format           |
| `adclip_campaign_status`      | Show manifest, costs, state of a campaign dir          |

## Policy checks

`policy.py` exposes `check(copy, brief)` returning `PolicyReport(violations, warnings)`.

Policy profiles:
- **default** — generic: no all-caps body, no emoji spam, no false scarcity
- **crypto** — no guaranteed returns, no FOMO, required risk disclosure if claims made
- **health** — no cure claims, no before/after, no "doctors hate this"
- **alcohol** — no minors visible, age-gating required, no health claims
- **financial_services** — no APR/APY without disclosure, no "guaranteed approval"

Each profile runs:
1. **Hard rules** (violations — dropped from pool)
2. **Soft rules** (warnings — included in report, variant still usable)

Platform-level auto-checks run regardless of profile: char limits, reserved-word matching (Meta restricted list), trademark flags.

## Cost estimation

`cost.estimate(brief)` returns:
- LLM tokens (copy gen × pool size × formats)
- fal.ai static image cost (Flux ≈ $0.02-0.04/img)
- fal.ai video cost (per-second × duration × pool count, per model)
- Total in USD

If `brief.budget_usd` is set, pipeline aborts before any paid call if estimate > budget. Estimator errs high — real cost ≤ estimate.

## Configuration

- `FAL_KEY` — fal.ai API key (same env var declip uses, one key works for both)
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` — LLM for copywriting; pluggable provider
- `ADCLIP_DEFAULT_BUDGET_USD` — optional global cap
- `ADCLIP_IMAGE_MODEL` — default fal image model (e.g. `fal-ai/flux/dev`)
- `ADCLIP_VIDEO_MODEL` — default fal video model (e.g. `kling-2.6`)

## Testing strategy

- **Schema tests** — AdBrief validation, format spec lookups, char-limit compliance
- **Policy tests** — hand-crafted copy that trips each policy profile; assert violations caught
- **Scoring tests** — fixtures of known-good and known-bad variants; scorer must rank correctly
- **Compose tests** — AdBrief → render plan JSON output stable across runs
- **Integration (gated on FAL_KEY)** — small end-to-end run with cheap models (LTX for video, Flux schnell for images), asserts output files exist and match expected specs

Rendering tests reuse declip's existing harness (cloned).

## Dependencies

Matches declip pyproject minus what we don't need, plus LLM clients:

```toml
dependencies = [
    "click>=8.1",
    "pydantic>=2.0",
    "av>=12.0",
    "numpy>=1.26",
    "Pillow>=10.0",
    "mcp>=1.2.0",
    "fal-client>=0.13",
    "anthropic>=0.40",        # or openai, pluggable
    "faster-whisper>=1.0",    # captions
    "watchdog>=4.0",
]
```

External: `ffmpeg` (homebrew, same as declip).

Python venv: `.venv/` (Python 3.14, `pip install .`).

## Out of scope (explicit)

Flagged now so future scope-creep requests get routed to a separate project:

- **Ad platform upload** (push to Meta Ads Manager / Google Ads). adclip outputs files; humans or a separate tool upload.
- **Performance data ingestion** (pull CTR/CPC from Meta API to feedback-loop the optimizer). Valuable, but a different project — keeps adclip focused on generation.
- **Landing page generation.** Different problem, different tool.
- **A/B test orchestration.** Platforms handle this natively via DCO.
- **Video editing UI.** declip already has that job.

## Open questions — none blocking

All decisions for v0.1.0 made. Known future questions (do not resolve now):

- Should `policy.py` pull from a live Meta restricted-word list, or ship a snapshot?
- Should scoring use a local LLM (cheap, per CLAUDE.md routing rules) or the same copywriter model?
- LLM provider choice (Claude vs GPT vs local) — default to Claude for copy, but make pluggable.
