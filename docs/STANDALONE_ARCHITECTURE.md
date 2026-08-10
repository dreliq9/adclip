# adclip Standalone Product Contract

**Status:** Active architecture direction  
**Date:** 2026-08-07  
**Scope:** Product, model, runtime, storage, and migration boundaries

## Decision

adclip is a standalone, local-first, model-agnostic marketing creative
application. MCP is one interface into the application; it is not the
application architecture.

A normal user must be able to install and operate adclip without:

- an MCP host;
- another Adam Engineering repository;
- a manually authored JSON brief;
- a developer checkout;
- a particular model vendor;
- a cloud model, when suitable local models are configured.

Integrations with declip, FCP-MCP, youtube-mcp-v2, the Abductive Reasoning
Kernel, advertising platforms, and hosted model vendors may improve individual
stages. They must not be prerequisites for the baseline campaign workflow.

## Product thesis

adclip owns the complete marketing-creative loop:

```text
Brand and source material
  -> campaign intent
  -> creative hypotheses
  -> concepts and controlled variants
  -> review and approval
  -> platform-valid exports or deployment
  -> observed performance
  -> next experiment
```

When campaigns are produced **inside Grok Build** with Imagine scene plates
and code typography (rather than only `adclip run` media providers), use the
operator loop in [`GROK_BUILD_CREATIVE_WORKFLOW.md`](GROK_BUILD_CREATIVE_WORKFLOW.md)
for inventory, scorecard review, and targeted plate/type regeneration.

The open local core should remain useful on its own. Hosted services may later
add collaboration, managed inference, OAuth account connections, scheduled
performance synchronization, and remote access.

## Standalone acceptance criteria

A clean installation is considered product-level standalone when it can:

1. Start without an MCP client.
2. Create and persist a brand profile.
3. Import product information and source assets.
4. Plan a campaign from a guided interface.
5. Generate copy through any configured compatible text provider/model.
6. Generate or import static and video source media.
7. Compose at least one platform-valid static ad and one short-form video.
8. Let a human edit, compare, approve, reject, and regenerate variants.
9. Export a complete campaign package without a platform account.
10. Resume interrupted generation without losing completed artifacts.
11. Record provider, model, prompt version, seed, source lineage, cost, and
    policy results for every generated asset.
12. Run with explicit connectivity modes, including enforceable offline and
    air-gapped modes with local inference.
13. Replace a text, image, or video model without changing campaign workflow
    code or external interface contracts.

The current repository already satisfies parts of items 1, 5, 7, 9, 12, and
13. The migration builds a persistent product around those working primitives
rather than replacing them.

## Architectural rules

### 1. Core application code must not depend on transports

The domain and application layers may not import from `adclip.mcp`, a web UI,
or a future HTTP server. Transport adapters call application services.

```text
CLI ----\
MCP -----+--> AdclipApplication --> domain/workflows/providers/storage
HTTP ----+
Web -----/
```

Existing JSON contracts remain available through compatibility methods while
new callers can operate on typed domain objects.

### 2. Workflows depend on capabilities, not model vendors

Text, image, video, speech, transcription, embedding, and vision are
capabilities. Provider and model are separate selections:

```text
workflow -> capability -> provider adapter -> selected model
```

Campaign, policy, scoring, experiment, and interface modules may not branch on
vendor or model names. A new provider must be registered behind a neutral
contract; adding one must not require editing campaign logic.

Provider metadata declares:

- supported modalities;
- structured-output behavior;
- whether model override is supported;
- whether local inference is supported;
- network scope;
- potential paid-API use;
- host-session dependence.

The first neutral text contract is `TextGenerationProvider`. Existing legacy
LLM classes structurally implement it. `LLM*` names remain compatibility
aliases while new code uses text-provider terminology.

The generic `openai-compatible` adapter speaks `/v1/chat/completions` directly,
allowing local servers and hosted gateways without taking a vendor SDK
dependency. See `docs/MODEL_PROVIDERS.md`.

### 3. Provider and model configuration are independent

Configuration precedence is explicit argument, provider-specific environment,
global modality environment, then adapter default.

```text
ADCLIP_TEXT_PROVIDER
ADCLIP_TEXT_MODEL
ADCLIP_IMAGE_PROVIDER
ADCLIP_IMAGE_MODEL
ADCLIP_VIDEO_PROVIDER
ADCLIP_VIDEO_MODEL
```

The compatibility default remains `claude-cli`, but no architecture contract
assumes Claude or any other model family.

### 4. External projects are optional accelerators

Every core workflow receives a competent native implementation:

| Workflow | Native adclip responsibility | Optional enhancement |
| --- | --- | --- |
| Brand ingestion | Website/files/assets to BrandKit | Specialized crawlers |
| Copy | Structured campaign copy generation | Expert model adapters |
| Static creative | Templates, overlays, resizing, export | Remote image models |
| Video creative | Script, clip, captions, simple scenes | declip / FCP-MCP |
| Source ingestion | Upload, URL, transcript, timestamps | youtube-mcp-v2 |
| Experiment planning | Controlled factors and simple recommendation | Abductive Reasoning Kernel |
| Policy | Versioned native policy packs | Legal/compliance integrations |
| Performance | Native observation and experiment model | Attribution platforms |

An optional adapter may replace or extend a native implementation, but it may
not be the only route through a baseline workflow.

### 5. Files remain portable; the database becomes authoritative

Campaign directories remain a transparent export format, but they cannot carry
all future application state.

```text
~/.local/share/adclip/
  adclip.db
  artifacts/sha256/
  providers.toml
  logs/
```

SQLite will hold brands, campaigns, concepts, variants, jobs, approvals,
deployments, observations, provider configurations, and migrations. Binary
media will live in a content-addressed artifact store. Campaign-directory
exports will be projections with schema versions and checksums.

### 6. Long-running work is job-oriented

Generation and import operations use durable jobs:

```text
PLANNED -> VALIDATING -> AUTHORIZED -> RUNNING
        -> READY_FOR_REVIEW | PARTIAL | FAILED | CANCELLED
```

Each stage is checkpointed. Jobs require idempotency keys, retry policy,
cancellation, progress events, and resumability after restart. Provider/model
selection is frozen into the job record before execution.

### 7. Paid and network actions require explicit policy

| Mode | Intended behavior |
| --- | --- |
| `online` | External providers may run; paid providers still require authorization. |
| `restricted_network` | External providers require an explicit allowlist entry. |
| `offline` | External network providers are refused; loopback model servers are allowed. |
| `air_gapped` | External providers and host delegation are refused; loopback inference remains allowed. |

```bash
ADCLIP_RUNTIME_MODE=offline
ADCLIP_ALLOWED_NETWORK_PROVIDERS=claude-cli
ADCLIP_ALLOW_LIVE_APIS=1
ADCLIP_ALLOW_HOST_SESSIONS=0
```

Provider requirements are checked before construction or invocation.
Endpoint-configurable adapters must re-check after loading the endpoint because
a static registry entry cannot determine whether an HTTP server is local.
Provider-side billing gates remain defense in depth.

## Target module layout

```text
src/adclip/
  domain/
    brand.py
    source.py
    campaign.py
    concept.py
    creative.py
    experiment.py
    deployment.py
    observation.py

  application/
    services.py
    onboard_brand.py
    plan_campaign.py
    generate_creatives.py
    review_creatives.py
    export_campaign.py
    sync_performance.py
    propose_experiment.py

  providers/
    contracts.py
    registry.py
    openai_compatible.py
    text/
    image/
    video/
    speech/
    transcription/

  media/
    templates/
    layouts/
    render/
    captions/
    clipping/

  connectors/
    meta/
    google/
    tiktok/
    youtube/
    adcp/

  storage/
    database.py
    migrations/
    artifacts.py
    repositories.py

  interfaces/
    cli/
    mcp/
    http/
    web/
```

This is a destination, not a big-bang reorganization. Modules move only when a
real application or domain boundary exists.

## Migration sequence

### Milestone S0 — boundary and model abstraction

- [x] Establish the standalone product contract.
- [x] Add a transport-neutral `AdclipApplication` facade.
- [x] Make CLI and MCP sibling adapters over that facade.
- [x] Centralize provider resolution.
- [x] Add explicit runtime modes and provider requirement checks.
- [x] Distinguish local loopback inference from external network access.
- [x] Introduce a provider-neutral text-generation contract.
- [x] Separate provider selection from model selection.
- [x] Add a generic OpenAI-compatible local/hosted text adapter.
- [x] Add independent image and video model overrides.
- [x] Move fake media adapters out of the MCP package.
- [ ] Make the application service the only supported entry point for new
      workflows.

### Milestone S1 — persistent local application

- [ ] Add SQLite and schema migrations.
- [ ] Add content-addressed artifact storage.
- [ ] Introduce stable IDs and Manifest v2 lineage.
- [ ] Persist provider, model, endpoint class, and generation parameters.
- [ ] Implement durable generation jobs and checkpoints.
- [ ] Add `adclip project create`, `adclip job status`, `resume`, and `cancel`.
- [ ] Preserve current folder output as a portable export.
- [ ] Add persistent provider profiles rather than environment-only config.

### Milestone S2 — BrandKit and SourceLibrary

- [ ] Persistent BrandKit schema.
- [ ] Website ingestion and editable brand extraction.
- [ ] Source asset import with rights/provenance metadata.
- [ ] Product screenshots, reviews, claims, and substantiation records.
- [ ] CampaignBriefV2 with objective, offer, funnel, audience segments,
      landing page, budget, and success metric.

### Milestone S3 — local workbench

- [ ] `adclip serve` local HTTP runtime.
- [ ] Bundled browser interface.
- [ ] Provider/model configuration and health checks.
- [ ] Brand/source/campaign screens.
- [ ] Visual variant gallery and comparison.
- [ ] Editing, approval, rejection, and regeneration.
- [ ] Job progress and provider diagnostics.

### Milestone S4 — native creative system

- [ ] Platform-specific asset bundles.
- [ ] Creative recipes and controlled variation axes.
- [ ] Template-driven static layouts.
- [ ] Native short-form scene assembly, captions, thumbnails, and audio.
- [ ] Versioned platform and policy packs.
- [ ] Message-match checks against landing pages.
- [ ] Promote image/video bindings to full registries when a second production
      provider exists.

### Milestone S5 — learning loop

- [ ] Read-only Meta performance connector.
- [ ] Stable deployment-to-creative lineage.
- [ ] Performance observations with attribution context.
- [ ] Uncertainty-aware comparisons and minimum-evidence thresholds.
- [ ] Fatigue detection.
- [ ] Native next-test recommendation.
- [ ] Optional Abductive Reasoning Kernel adapter.

### Milestone S6 — safe activation

- [ ] Paused/draft campaign creation.
- [ ] Complete launch diff and human approval token.
- [ ] Budget, account, objective, audience, placement, and schedule checks.
- [ ] Idempotent publish, pause, and rollback.
- [ ] Immutable deployment audit log.

## Near-term non-goals

- A general-purpose nonlinear video editor
- A Canva/Figma-class design surface
- CRM and email automation
- Full landing-page generation
- Autonomous ad spending without approval
- Training or serving a proprietary foundation model inside adclip
- Claims that an LLM quality score predicts conversion performance

## Compatibility policy

- Existing CLI commands and MCP tool names remain stable while internals move.
- `--llm`, `--llm-model`, `--image`, and `--video` remain aliases for neutral
  CLI names.
- Current campaign directories remain readable.
- JSON brief methods remain available until a versioned replacement and
  migration path exist.
- `LLM*` registry and method names remain compatibility aliases.
- Claude CLI, MCP sampling, Anthropic, OpenAI-compatible, fal.ai, and fake
  providers remain adapters; none is allowed to become an application-layer
  vendor dependency.
- New code targets `AdclipApplication` and neutral provider contracts, not
  private functions under `adclip.mcp`.

## Definition of success

The architecture succeeds when adclip can be used as:

1. a standalone local marketing application;
2. an MCP-accessible tool controlled by an agent;
3. a composable component in a broader media and reasoning ecosystem;
4. a model-neutral workflow whose inference stack can be replaced without
   rewriting campaign logic.

No one mode or model vendor should be required to make the others work.
