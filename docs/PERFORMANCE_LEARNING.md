# Performance Learning Foundation

**Status:** Active read-only learning foundation  
**Date:** 2026-08-07

## Decision

adclip owns creative identity, deployment lineage, normalized performance
observations, and explicit experiment hypotheses. Ad platforms own delivery.
Connectors are adapters over that boundary.

The first connector is Meta and is deliberately **read-only**.

```text
adclip creative
  -> exact artifact identity
  -> deployment mapping
  -> external ad ID
  -> read-only platform insights
  -> normalized observation
  -> descriptive comparison
  -> explicit experiment evidence
  -> next-test recommendation
```

## Stable creative lineage

A metric is useful only if it can be joined to the exact creative that produced
it. Campaign manifests therefore carry:

```text
campaign_id      cmp_...
creative_id      crv_...
variant_id       v01
artifact_sha256  ...
```

`campaign_id` is stable and portable. If a copied campaign directory loses its
hidden `.adclip_campaign.json`, adclip restores the identity from the manifest.

When a rendered artifact exists, `creative_id` incorporates its SHA-256. If
`v01` is regenerated in place, the replacement bytes receive a new creative ID
instead of silently inheriting historical performance.

A deployment mapping snapshots:

```text
deployment_id
adclip campaign_id
adclip creative_id
variant_id
artifact path/hash
platform
account_id
external campaign/ad-set/ad/creative IDs
external status/name
last sync time
```

The mapping is explicit. adclip does not guess that visually similar files are
the same creative. A Meta account/ad pair may not be silently relinked to a
different local creative; the second link is rejected rather than overwriting
historical lineage.

## Portable storage

Until SQLite becomes authoritative:

```text
campaign/
  .adclip_campaign.json
  manifest.json
  performance/
    deployments.json
    observations.json
    experiments.json
```

Re-syncing the same deployment, exact date window, and action-reporting time
replaces the deterministic observation record rather than duplicating it.

## Meta read-only connector

The Meta adapter only implements HTTP GET. It reads:

1. explicit linked-ad metadata for identity verification;
2. `/{ad_id}/insights` for the requested date window.

Sync verifies both the returned account ID and returned ad ID before accepting
observations.

Normalized metrics include:

```text
impressions
reach
clicks
outbound_clicks
spend
actions[action_type]
action_values[action_type]
video thruplay / 25 / 50 / 75 / 95 / 100 percent metrics
currency
action_report_time
```

Platform action names remain intact instead of being guessed into a universal
conversion taxonomy.

### Configuration

```text
ADCLIP_META_ACCESS_TOKEN
META_ACCESS_TOKEN            compatibility fallback
ADCLIP_META_API_VERSION      default: v24.0
ADCLIP_META_BASE_URL         default: https://graph.facebook.com
ADCLIP_META_TIMEOUT          default: 30 seconds
```

The API version is configurable and must be advanced only with adapter/test
updates. Tokens are never persisted into campaign artifacts or returned by
reports.

### Runtime behavior

```text
online                 allowed
restricted_network     requires meta-performance in allowlist
offline                blocked
air_gapped             blocked
```

Read-only Insights retrieval does not use the paid-generation authorization
flag because it is not a generative provider call.

## Performance workflow

Link an existing Meta ad:

```bash
adclip performance link-meta ./campaign \
  --variant-id v01 \
  --account-id act_123456 \
  --ad-id 987654321
```

Sync one exact measurement window:

```bash
export ADCLIP_META_ACCESS_TOKEN=...

adclip performance sync-meta ./campaign \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion
```

A stored measurement window is the tuple:

```text
(since, until, action_report_time)
```

`conversion` and `impression` attribution rows for the same dates are never
silently summed. If an explicit date range has more than one stored
`action_report_time`, report/compare require an explicit selector:

```bash
adclip performance report ./campaign \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion

adclip performance compare ./campaign \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion \
  --metric ctr
```

Without dates, adclip chooses the latest exact date window and prefers its
`conversion` attribution row when present. If the latest dates contain multiple
non-conversion attribution modes, the caller must choose explicitly.

Initial descriptive metrics:

```text
ctr                 clicks / impressions
outbound_ctr        outbound clicks / impressions
cpc                 spend / clicks
cpm                 spend * 1000 / impressions
impressions
clicks
action_rate         selected action count / clicks
cost_per_action     spend / selected action count
roas                selected action value / spend
```

Reports also preserve impression-normalized action rates separately. Reach is
marked non-additive.

## Experiment layer

See [`EXPERIMENTS.md`](EXPERIMENTS.md) for the full evidence contract.

A declared experiment snapshots:

```text
hypothesis
changed factor
control exact creative + artifact hash + factor value
treatment exact creative + artifact hash + factor value
primary metric
expected direction
minimum denominator/events per arm
confidence level
```

Factor values are included in the deterministic experiment identity so
re-declaring the same creatives/factor/metric with different treatment/control
values cannot silently overwrite an earlier record.

Create one:

```bash
adclip performance experiment-create ./campaign \
  --name "Hook CTR test" \
  --hypothesis "A contrarian hook increases CTR" \
  --changed-factor hook \
  --control-variant v01 \
  --treatment-variant v02 \
  --control-value "plain benefit" \
  --treatment-value "contrarian challenge" \
  --metric ctr
```

Evaluate an exact window:

```bash
adclip performance experiment-evaluate ./campaign \
  --experiment-id exp_... \
  --since 2026-08-01 \
  --until 2026-08-07
```

Request the next controlled action:

```bash
adclip performance next-test ./campaign \
  --experiment-id exp_... \
  --since 2026-08-01 \
  --until 2026-08-07
```

### Evidence semantics

Inferential verdicts are limited to controlled rate comparisons with explicit
aggregate numerators and denominators:

```text
CTR            clicks / impressions
outbound CTR   outbound clicks / impressions
action rate    actions / clicks
```

Each arm receives a Wilson interval and the treatment-control difference uses a
conservative Newcombe-style Wilson bound construction. Both arms must meet the
experiment's declared minimum denominator and event thresholds before output may
say `supported` or `contradicted`. If an action count exceeds its click
denominator, binomial action-rate inference is refused.

`observational_comparison` remains descriptive even when the rate confidence
interval excludes zero:

```text
inferential: false
verdict: inconclusive
reason: observational_comparison_is_descriptive_only
```

Its intervals may still be returned for inspection, but the next-test planner
routes the user toward a stronger measurement design rather than declaring a
winner.

CPA and ROAS remain descriptive because aggregate totals do not provide enough
variance information for a responsible confidence interval.

Every experiment evaluation currently returns:

```text
causal_claim: false
```

A declared single-factor creative difference is not proof that auction,
audience, placement, timing, attribution, and delivery conditions were
randomized.

## Next-test behavior

The deterministic evidence planner can return:

```text
replicate_supported_factor
revise_changed_factor
collect_more_evidence
improve_measurement_design
replicate_or_extend
```

It does not invent a new marketing claim from thin evidence. Its job is to
separate what the observations support from what should be tested next. A later
abductive planner can propose novel hypotheses on top of this evidence layer.

## MCP tools

Performance ingestion:

```text
adclip_performance_link_meta
adclip_performance_deployments
adclip_performance_sync_meta
adclip_performance_report
adclip_performance_compare
```

`adclip_performance_report` and `adclip_performance_compare` accept
`action_report_time` for attribution-window disambiguation.

Experiments:

```text
adclip_experiment_create
adclip_experiments
adclip_experiment_evaluate
adclip_experiment_next_test
```

CLI and MCP share transport-neutral application services.

## Interpretation rules

- Exact `(since, until, action_report_time)` windows are compared to exact
  windows.
- Different attribution reporting times are never silently added together.
- Overlapping date periods are stored but not silently summed.
- Rankings alone never establish causal lift.
- Observational comparisons never receive inferential supported/contradicted
  verdicts.
- Controlled experiment verdicts require declared minimum evidence.
- CPA/ROAS direction is not statistical significance.
- Meta reach is not additive across ads.
- Regenerated creative bytes receive new creative identities.
- One external Meta ad cannot silently change which local creative it represents.

## Next steps

1. SQLite-backed campaign/deployment/observation/experiment persistence while
   retaining portable JSON projections.
2. Verified randomized-assignment metadata and stronger causal semantics.
3. Automatic creative-attribute extraction to audit declared single-factor
   tests.
4. Experiment-aware generation that locks non-tested factors.
5. Fatigue/change-point analysis over non-overlapping windows.
6. Google Ads and TikTok connectors using the same observation schema.
7. ESP/email performance observations.
8. Event-level or variance-aware CPA/ROAS inference.
9. Optional abductive next-test planning grounded in the deterministic evidence
   result.
10. Only after the read/learning loop is trustworthy, draft/paused activation
    with separate explicit human authorization.
