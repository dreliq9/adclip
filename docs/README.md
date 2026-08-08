# adclip documentation

adclip is a standalone, model-routed marketing creative and learning engine. The
repository now spans creative generation, responsive email authoring,
performance ingestion, explicit experiments, and evidence-aware next-test
recommendations. This page is the map for that surface.

## Start here

- [`QUICKSTART.md`](QUICKSTART.md) — install, run a zero-cost creative workflow,
  render email, and exercise the synthetic learning loop.
- [`../examples/README.md`](../examples/README.md) — runnable example catalog.
- [`../README.md`](../README.md) — product overview and command reference.
- [`../LLM.md`](../LLM.md) — model-neutral implementation guidance for AI agents
  and contributors working on the repository.

## Product and architecture

- [`STANDALONE_ARCHITECTURE.md`](STANDALONE_ARCHITECTURE.md) — product contract,
  layering rules, runtime boundaries, persistence direction, and roadmap.
- [`MODEL_PROVIDERS.md`](MODEL_PROVIDERS.md) — text-provider abstraction and
  local/hosted provider configuration.
- [`MODEL_ROUTING.md`](MODEL_ROUTING.md) — task routes for image/video models,
  explicit overrides, fallbacks, and bake-offs.

## Campaign capabilities

- [`EMAIL_CAMPAIGNS.md`](EMAIL_CAMPAIGNS.md) — structured email sequences,
  responsive HTML/text rendering, block editing, linting, and portable export.
- [`PERFORMANCE_LEARNING.md`](PERFORMANCE_LEARNING.md) — creative/deployment
  lineage, read-only Meta Insights ingestion, attribution-safe reporting, and
  normalized observations.
- [`EXPERIMENTS.md`](EXPERIMENTS.md) — explicit hypotheses, changed-factor
  lineage, evidence thresholds, confidence semantics, and next-test behavior.

## Current lifecycle

```text
campaign brief
    |
    +--> copy / image / video routes
    |        |
    |        +--> portable creative artifacts + provenance
    |
    +--> email sequence
    |        |
    |        +--> message JSON + HTML + text + headers + lint
    |
    +--> deployment mapping
             |
             +--> read-only performance observations
                       |
                       +--> descriptive comparison
                       |
                       +--> explicit experiment
                                  |
                                  +--> supported / contradicted / inconclusive
                                  |
                                  +--> next-test recommendation
```

MCP, CLI, and future HTTP/web interfaces are adapters over application services;
none of them owns the campaign model.

## Implemented now vs planned

### Implemented

- transport-neutral application services;
- CLI and MCP interfaces;
- provider/model-independent text generation;
- task-oriented image/video routing and model bake-offs;
- static, text, and short-form video generation paths;
- responsive email generation, rendering, linting, and block editing;
- stable campaign/creative/deployment lineage;
- read-only Meta performance synchronization;
- attribution-safe reporting by `(since, until, action_report_time)`;
- explicit creative experiments with conservative rate inference;
- deterministic evidence-aware next-test recommendations.

### Still planned

- SQLite as authoritative state plus migrations;
- content-addressed global artifact storage and durable jobs;
- BrandKit and SourceLibrary;
- bundled local browser workbench;
- Google Ads, TikTok, and ESP performance connectors;
- creative-attribute extraction and experiment-aware controlled generation;
- fatigue/change-point analysis;
- variance-aware CPA/ROAS inference;
- separately authorized draft/paused activation.

## Safety conventions

- Fake providers are deterministic and preferred for examples/tests.
- Potentially paid generation requires `ADCLIP_ALLOW_LIVE_APIS=1`.
- `offline` and `air_gapped` runtime modes refuse external network providers.
- The current Meta performance connector is read-only.
- Performance rankings are descriptive unless an explicit experiment contract
  permits an inferential rate verdict.
- Experiment evaluations currently retain `causal_claim: false` even when the
  statistical evidence supports the declared treatment direction.
