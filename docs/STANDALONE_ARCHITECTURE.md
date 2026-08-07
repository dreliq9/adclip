# adclip Standalone Product Contract

**Status:** Active architecture direction  
**Date:** 2026-08-07  
**Scope:** Product boundary, runtime boundary, and migration sequence

## Decision

adclip is a standalone, local-first marketing creative application. MCP is one
interface into the application; it is not the application architecture.

A normal user must be able to install and operate adclip without:

- an MCP host;
- another Adam Engineering repository;
- a manually authored JSON brief;
- a developer checkout;
- a particular model vendor.

Integrations with declip, FCP-MCP, youtube-mcp-v2, the Abductive Reasoning
Kernel, and advertising platforms may improve individual stages. They must not
be prerequisites for the baseline campaign workflow.

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

The open local core should remain useful on its own. Hosted services may later
add collaboration, managed inference, OAuth account connections, scheduled
performance synchronization, and remote access.

## Standalone acceptance criteria

A clean installation is considered product-level standalone when it can:

1. Start without an MCP client.
2. Create and persist a brand profile.
3. Import product information and source assets.
4. Plan a campaign from a guided interface.
5. Generate copy through any configured text provider.
6. Generate or import static and video source media.
7. Compose at least one platform-valid static ad and one short-form video.
8. Let a human edit, compare, approve, reject, and regenerate variants.
9. Export a complete campaign package without a platform account.
10. Resume an interrupted generation run without losing completed artifacts.
11. Record provider, model, prompt version, seed, source lineage, cost, and
    policy results for every generated asset.
12. Run with explicit connectivity modes, including an enforceable offline
    mode.

The current repository already satisfies parts of items 1, 5, 7, and 9 through
its CLI, generation pipeline, renderers, and campaign folders. The migration
below builds the persistent application around those working primitives rather
than replacing them.

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

This branch introduces `AdclipApplication` as the first application-service
boundary. Existing JSON contracts remain available through compatibility
methods while new callers can operate on typed domain objects.

### 2. Providers are capabilities, not hard-coded branches

Text, image, video, speech, transcription, embedding, and vision providers
must be selected through registries or capability interfaces. Provider
metadata must declare operational requirements such as:

- network access;
- paid API authorization;
- host-session dependence;
- local executable dependence;
- supported media or structured-output capabilities.

The first registry covers existing LLM providers. Image and video adapters are
moved out of MCP wiring as a precursor to full media registries.

### 3. External projects are optional accelerators

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

### 4. Files remain portable; the database becomes authoritative

Campaign directories are a valuable transparent export format. They should
remain readable and portable, but they cannot carry all future application
state.

The target local layout is:

```text
~/.local/share/adclip/
  adclip.db
  artifacts/sha256/
  providers.toml
  logs/
```

SQLite will hold brands, campaigns, concepts, variants, jobs, approvals,
deployments, observations, and migrations. Binary media will live in a
content-addressed artifact store. A campaign-directory export will be a
projection of that state with checksums and schema versions.

### 5. Long-running work is job-oriented

Generation and import operations must use durable jobs:

```text
PLANNED -> VALIDATING -> AUTHORIZED -> RUNNING
        -> READY_FOR_REVIEW | PARTIAL | FAILED | CANCELLED
```

Each stage must be checkpointed. Jobs require idempotency keys, retry policy,
cancellation, progress events, and resumability after process restart.

### 6. Paid and network actions require explicit policy

The application exposes four runtime modes:

| Mode | Intended behavior |
| --- | --- |
| `online` | Network providers may run; paid providers still require authorization. |
| `restricted_network` | Only providers named in an explicit allowlist may use the network. |
| `offline` | Network-requiring providers are refused. |
| `air_gapped` | Network providers and implicit host-session delegation are refused by default. |

Configuration:

```bash
ADCLIP_RUNTIME_MODE=offline
ADCLIP_ALLOWED_NETWORK_PROVIDERS=claude-cli
ADCLIP_ALLOW_LIVE_APIS=1
ADCLIP_ALLOW_HOST_SESSIONS=0
```

Runtime policy is enforced before provider construction. Existing provider-side
billing gates remain defense in depth.

## Target module layout

The repository should evolve incrementally toward:

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
    registry.py
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

This is a destination, not a mandatory big-bang reorganization. Modules move
only when a real application or domain boundary exists.

## Migration sequence

### Milestone S0 — boundary extraction

- [x] Establish this standalone product contract.
- [x] Add a transport-neutral `AdclipApplication` facade.
- [x] Make CLI and MCP sibling adapters over that facade.
- [x] Centralize existing LLM provider resolution.
- [x] Add explicit runtime modes and provider requirement checks.
- [x] Move fake media adapters out of the MCP package.
- [ ] Make the application service the only supported entry point for new
      workflows.

### Milestone S1 — persistent local application

- [ ] Add SQLite and schema migrations.
- [ ] Add content-addressed artifact storage.
- [ ] Introduce stable IDs and Manifest v2 lineage.
- [ ] Implement durable generation jobs and checkpoints.
- [ ] Add `adclip project create`, `adclip job status`, `resume`, and `cancel`.
- [ ] Preserve the current folder output as a portable export.

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

The standalone direction does not mean building every marketing product at
once. The following remain outside the near-term core:

- a general-purpose nonlinear video editor;
- a Canva/Figma-class design surface;
- CRM and email automation;
- full landing-page generation;
- autonomous ad spending without approval;
- unsupported claims that LLM quality scores predict conversion performance.

## Compatibility policy

- Existing CLI commands and MCP tool names remain stable while internals move.
- Current campaign directories remain readable.
- JSON brief methods remain available until a versioned replacement and
  migration path exist.
- `claude-cli`, MCP sampling, Anthropic, fal.ai, and fake providers remain
  supported adapters; none is allowed to become an application-layer import.
- New code should target `AdclipApplication`, not private functions under
  `adclip.mcp`.

## Definition of success

The architecture succeeds when adclip can be used in three equally valid ways:

1. a standalone local marketing application;
2. an MCP-accessible tool controlled by an agent;
3. a composable component in a broader media and reasoning ecosystem.

No one mode should be required to make the other two work.
