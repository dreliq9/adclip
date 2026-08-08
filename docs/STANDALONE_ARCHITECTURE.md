# adclip Standalone Product Contract

**Status:** Active architecture direction  
**Date:** 2026-08-07  
**Scope:** Product, model, runtime, storage, learning, and integration boundaries

## Decision

adclip is a standalone, local-first, model-routed marketing creative and
learning application. MCP is one interface into the application; it is not the
application architecture.

A normal user should be able to install and operate the core without:

- an MCP host;
- another Adam Engineering repository;
- a particular model vendor;
- a cloud model, when suitable local models are configured;
- a live ad account for generation, email authoring, or synthetic learning;
- a proprietary SaaS as the source of truth for campaign creative.

Integrations with declip, FCP-MCP, youtube-mcp-v2, the Abductive Reasoning
Kernel, advertising platforms, ESPs, and hosted model vendors may improve
individual stages. They must remain replaceable adapters around a useful local
core.

## Product thesis

adclip owns the creative-learning loop:

```text
Brand and source material
  -> campaign intent
  -> creative hypotheses
  -> concepts and controlled variants
  -> copy / image / video / email artifacts
  -> review and approval
  -> platform-valid export or deployment mapping
  -> observed performance
  -> explicit experiment evidence
  -> next test
```

The open local core should remain useful on its own. Hosted services may later
add collaboration, managed inference, OAuth account connections, scheduled
performance synchronization, and remote access without becoming the only way to
use the product.

## What is already true

The current repository already has meaningful portions of the target product:

- transport-neutral application services with CLI and MCP adapters;
- provider/model-independent text generation;
- task-oriented image/video routing with explicit overrides and bake-offs;
- static, text, and short-form video generation paths;
- responsive email generation, rendering, linting, and stable block editing;
- portable campaign manifests and artifact-bound creative IDs;
- explicit local-to-platform deployment lineage;
- read-only Meta performance synchronization;
- attribution-safe exact-window reporting;
- explicit control/treatment experiments with changed-factor lineage;
- conservative confidence semantics for supported rate metrics;
- deterministic evidence-aware next-test recommendations;
- offline, air-gapped, restricted-network, and online runtime policies.

The remaining work is increasingly about persistence, brand/source context,
human workflow, additional connectors, and stronger experiment design rather
than basic campaign generation.

## Architectural rules

### 1. Core application code must not depend on transports

Domain/application modules may not import from `adclip.mcp`, a web UI, or a
future HTTP server. Transport adapters call application services.

```text
CLI -----\
MCP ------+--> application services --> domain / providers / connectors / storage
HTTP -----+
Web ------/
```

The current examples are concrete:

```text
AdclipApplication       creative generation and routing
EmailApplication        email authoring/render/edit/lint
PerformanceApplication  deployment lineage and read-only observations
ExperimentApplication   hypotheses, evidence, and next-test guidance
```

### 2. Workflows depend on capabilities and task routes, not vendors

Text, image, video, speech, transcription, embedding, and vision are
capabilities. Provider and model are separate selections.

```text
workflow -> capability / task route -> provider adapter -> selected model
```

Campaign, policy, scoring, experiment, and interface code may not branch on
vendor or model names. Provider adapters own vendor request/response schemas.

The generic `openai-compatible` text adapter allows local servers and hosted
gateways without taking a vendor SDK dependency. See
[`MODEL_PROVIDERS.md`](MODEL_PROVIDERS.md).

### 3. Routes are marketing intent, not model aliases

The image/video route layer describes jobs such as:

```text
text-heavy
brand-control
bulk
premium
multi-shot
budget
```

A route may change its preferred model as evidence changes. Explicit
provider/model overrides remain authoritative. Fallback candidates are metadata;
another paid call must never be executed silently.

See [`MODEL_ROUTING.md`](MODEL_ROUTING.md).

### 4. External projects are optional accelerators

Every baseline workflow needs a competent native path.

| Workflow | Native adclip responsibility | Optional enhancement |
| --- | --- | --- |
| Brand ingestion | Future BrandKit + files/assets | Specialized crawlers |
| Copy | Structured provider-neutral generation | Expert adapters |
| Static creative | Native composition/export + routed generation | Remote image models |
| Video creative | Short-form generation/orchestration | declip / FCP-MCP |
| Source ingestion | Future SourceLibrary | youtube-mcp-v2 |
| Email | Structured messages + HTML/text/lint/edit | ESP delivery connectors |
| Experiment planning | Explicit changed factor + deterministic evidence | Abductive Reasoning Kernel |
| Performance | Deployment/observation model + Meta read connector | Attribution platforms |
| Activation | Future guarded draft/paused writes | Platform MCPs/connectors |

Optional adapters may replace or extend a native implementation, but they may
not become the sole source of campaign state.

### 5. Creative identity belongs to exact artifacts

Campaign and creative lineage must survive model changes and regeneration.
Current campaign manifests carry stable campaign identity and artifact-bound
creative identity.

```text
campaign_id      cmp_...
variant_id       v01
creative_id      crv_...
artifact_sha256  ...
```

When an artifact exists, its SHA-256 participates in creative identity. If a
variant is regenerated in place, the new bytes receive a new creative ID rather
than inheriting old performance.

Deployment mappings snapshot the creative ID and artifact hash that were
actually linked to an external ad.

### 6. Measurement context is part of the observation identity

Performance must not collapse attribution settings into one number. A stored
window is identified by at least:

```text
platform
external deployment
since
until
action_report_time
```

The current Meta path refuses to silently combine the same dates under different
attribution reporting times. Performance rankings are descriptive unless an
explicit experiment contract justifies a stronger rate verdict.

See [`PERFORMANCE_LEARNING.md`](PERFORMANCE_LEARNING.md).

### 7. Hypothesis is distinct from evidence

An experiment snapshots:

- the hypothesis statement;
- one declared changed factor;
- exact control and treatment creative IDs/artifact hashes;
- factor values;
- primary metric and expected direction;
- experiment design;
- evidence thresholds and confidence level.

`observational_comparison` remains descriptive and cannot produce a supported
inferential verdict. Current controlled rate evidence may produce
`supported`, `contradicted`, or `inconclusive`, but still reports
`causal_claim: false` because randomized delivery is not yet verified.

CPA and ROAS remain descriptive until event-level or variance-aware evidence is
available.

See [`EXPERIMENTS.md`](EXPERIMENTS.md).

### 8. Files remain portable; SQLite becomes authoritative

Campaign directories are useful transparent bundles, but they cannot carry all
future application state efficiently.

Target local state:

```text
~/.local/share/adclip/
  adclip.db
  artifacts/
    sha256/
  providers.toml
  logs/
```

SQLite should eventually hold brands, sources, campaigns, concepts, variants,
jobs, approvals, deployments, observations, experiments, provider
configurations, and migrations. Binary media should live in a content-addressed
artifact store.

Portable campaign directories remain projections with schema versions,
checksums, and enough identity to move between machines.

### 9. Long-running work is job-oriented

Generation, ingestion, and synchronization should converge on durable jobs:

```text
PLANNED -> VALIDATING -> AUTHORIZED -> RUNNING
        -> READY_FOR_REVIEW | PARTIAL | FAILED | CANCELLED
```

Jobs require idempotency keys, retry policy, cancellation, progress events, and
resumability. Provider/model selection is frozen into a job before execution.

### 10. Paid, network, and write actions are separate policy dimensions

Current runtime modes:

| Mode | Intended behavior |
| --- | --- |
| `online` | External network adapters may run; paid generation still needs authorization. |
| `restricted_network` | External providers/connectors require an allowlist entry. |
| `offline` | External network refused; loopback model servers allowed. |
| `air_gapped` | External providers and host delegation refused; loopback inference allowed. |

Potentially paid generation requires:

```text
ADCLIP_ALLOW_LIVE_APIS=1
```

That flag is not a generic network authorization. The Meta performance adapter,
for example, performs read-only network retrieval and is governed by runtime
network policy rather than the generation-spend gate.

Future ad-platform writes require a **separate explicit activation policy** with
account, budget, objective, audience, placement, schedule, diff, idempotency,
and human-approval checks.

## Current module direction

The repository is migrating toward these durable boundaries without a big-bang
reorganization:

```text
src/adclip/
  application/
    services.py
    email_services.py
    performance_services.py
    experiment_services.py

  providers/
    contracts.py
    registry.py
    media.py
    ...

  email/
    schema.py
    generate.py
    render.py
    edit.py
    lint.py

  performance/
    schema.py
    identity.py
    store.py
    analysis.py
    experiment.py

  connectors/
    meta_performance.py
    ... future platform adapters

  mcp/
    ... transport adapters

  storage/
    ... future authoritative persistence

  interfaces/
    ... future HTTP/web adapters
```

Domain modules should be introduced when a real boundary exists rather than
moving files solely to match a diagram.

## Roadmap

### S0 — application/model boundary — substantially complete

- [x] Standalone product contract.
- [x] Transport-neutral application services.
- [x] CLI and MCP sibling interfaces.
- [x] Runtime modes and provider requirement checks.
- [x] Provider-neutral text-generation contract.
- [x] Provider selection separate from model selection.
- [x] OpenAI-compatible and command-provider local paths.
- [x] Independent image/video route/model selection.
- [x] Fake providers outside MCP internals.
- [ ] Finish routing all remaining legacy/new workflows through application services.

### S1 — authoritative persistence — partially complete

- [ ] SQLite and schema migrations.
- [ ] Global content-addressed artifact store.
- [x] Stable campaign IDs.
- [x] Artifact-bound creative IDs.
- [x] Stable deployment/observation/experiment IDs.
- [x] Portable JSON projections for current performance/experiment state.
- [ ] Durable generation/synchronization jobs and checkpoints.
- [ ] Provider profiles stored outside environment-only configuration.
- [ ] Migration/versioning strategy for all persisted objects.

### S2 — BrandKit and SourceLibrary — not started

- [ ] Persistent BrandKit schema.
- [ ] Website/file ingestion and editable brand extraction.
- [ ] Source assets with rights/provenance metadata.
- [ ] Product screenshots, reviews, claims, and substantiation records.
- [ ] Campaign brief evolution with objectives, offer, funnel, segments, landing page, and success metric.

### S3 — local workbench — not started

- [ ] `adclip serve` local HTTP runtime.
- [ ] Bundled browser interface.
- [ ] Provider/model configuration and health checks.
- [ ] Brand/source/campaign screens.
- [ ] Visual variant gallery and comparison.
- [ ] Email block review/edit experience.
- [ ] Performance/experiment views.
- [ ] Approval, rejection, regeneration, and job progress.

### S4 — richer native creative system — in progress

- [x] Cross-platform static/text/video format paths.
- [x] Task-oriented media routing.
- [x] Email structured authoring/render/edit/lint.
- [ ] Creative recipes with explicit controlled variation axes.
- [ ] Template-driven static layout library.
- [ ] Native short-form scene assembly, captions, thumbnails, and audio controls.
- [ ] Versioned platform/policy packs.
- [ ] Message-match checks against landing pages.
- [ ] Executable reference-image/vector/multi-reference/edit routes.

### S5 — learning loop foundation — substantially complete

- [x] Read-only Meta performance connector.
- [x] Stable deployment-to-creative lineage.
- [x] Performance observations with attribution context.
- [x] Exact-window descriptive comparison.
- [x] Explicit experiment/hypothesis objects.
- [x] Minimum-evidence thresholds for rate experiments.
- [x] Conservative rate confidence intervals.
- [x] Observational-vs-controlled evidence separation.
- [x] Deterministic evidence-aware next-test recommendation.
- [ ] Verified randomized-assignment metadata.
- [ ] Creative-attribute extraction to audit single-factor claims.
- [ ] Experiment-aware generation that locks non-tested factors.
- [ ] Fatigue/change-point analysis.
- [ ] Event-level or variance-aware CPA/ROAS inference.
- [ ] Optional Abductive Reasoning Kernel adapter.

### S6 — broader observation connectors — next integration phase

- [ ] Google Ads performance adapter.
- [ ] TikTok Ads performance adapter.
- [ ] ESP/email performance adapter.
- [ ] Cross-platform semantic metric/action mapping where explicit and auditable.
- [ ] Scheduled synchronization once durable jobs exist.

### S7 — safe activation — deliberately later

- [ ] Paused/draft campaign creation only.
- [ ] Complete launch diff and human approval token.
- [ ] Budget/account/objective/audience/placement/schedule checks.
- [ ] Idempotent publish, pause, and rollback.
- [ ] Immutable deployment audit log.

## Near-term non-goals

- A general-purpose nonlinear video editor
- A Canva/Figma-class infinite design surface
- A CRM or full ESP
- Full landing-page generation
- Autonomous ad spending without approval
- Training/serving a proprietary foundation model inside adclip
- Claims that LLM quality scores predict conversion performance
- Treating observational creative winners as proven causal effects

## Compatibility policy

- Existing CLI commands and MCP tool names remain stable while internals move.
- `--llm`, `--llm-model`, `--image`, and `--video` remain compatibility aliases.
- Current campaign directories remain readable and should gain migration paths
  when schemas evolve.
- `LLM*` names remain compatibility aliases while new code uses neutral
  provider terminology.
- Claude CLI, MCP sampling, Anthropic, OpenAI-compatible, fal.ai, direct OpenAI,
  and fake providers remain adapters, not application-layer dependencies.
- New workflows should target application services and neutral contracts, not
  private functions under `adclip.mcp`.

## Definition of success

The architecture succeeds when adclip works coherently as:

1. a standalone local marketing application;
2. an MCP-accessible capability for agents;
3. a portable creative/evidence system that survives vendor changes;
4. a composable component in a broader media and reasoning ecosystem;
5. a learning loop that distinguishes hypothesis, observation, inference, and
   action rather than collapsing them into one model recommendation.

No one interface, model vendor, ad platform, or SaaS should be required to make
the rest of the system useful.
