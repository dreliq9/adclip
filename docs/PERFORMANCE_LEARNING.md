# Performance Learning Foundation

**Status:** Active read-only foundation  
**Date:** 2026-08-07

## Decision

adclip owns creative identity and normalized performance observations. Ad
platforms own delivery. Performance connectors are adapters over that boundary.

The first connector is Meta and is deliberately **read-only**. It can inspect an
explicitly linked ad and read its Insights data. It has no campaign, ad-set, ad,
budget, targeting, or creative mutation method.

```text
adclip creative
  -> deployment mapping
  -> external ad ID
  -> read-only platform insights
  -> normalized observation
  -> descriptive comparison
  -> future experiment inference
```

## Why explicit deployment lineage comes first

A metric is not useful to the creative-learning loop unless it can be joined to
the exact artifact that produced it. New adclip campaign manifests therefore
carry:

```text
campaign_id  cmp_...
creative_id  crv_...
variant_id   v01
```

`campaign_id` is created once in `.adclip_campaign.json`. `creative_id` is
deterministic from campaign, variant, and format. Old manifests are backfilled
when performance features first read them.

A deployment mapping then records:

```text
deployment_id
a dclip campaign_id
adclip creative_id
variant_id
platform
account_id
external campaign/ad-set/ad/creative IDs
external status/name
last sync time
```

The mapping is explicit. adclip does not guess that two visually similar assets
are the same creative.

## Portable storage

Before SQLite becomes authoritative, performance state remains transparent and
portable inside the campaign directory:

```text
campaign/
  .adclip_campaign.json
  manifest.json
  performance/
    deployments.json
    observations.json
```

Re-syncing the same deployment and exact date window updates the deterministic
observation ID rather than creating duplicate measurements.

## Meta read-only connector

The connector uses bearer-authenticated GET requests against the Meta Marketing
API. It reads:

1. ad metadata for identity verification and external lineage;
2. `/{ad_id}/insights` for the requested date window.

The normalized metric set includes:

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
```

Meta action names are preserved rather than prematurely mapped into a universal
conversion taxonomy. A later semantic layer can map platform action types only
when the mapping is explicit and auditable.

### Configuration

```text
ADCLIP_META_ACCESS_TOKEN     required for live sync
META_ACCESS_TOKEN            compatibility fallback
ADCLIP_META_API_VERSION      default: v24.0
ADCLIP_META_BASE_URL         default: https://graph.facebook.com
ADCLIP_META_TIMEOUT          default: 30 seconds
```

`v24.0` is a compatibility default, not a claim that it will always be Meta's
latest version. Keep the version configurable and advance it only with adapter
and test updates.

A read-capable Marketing API token is required. `ads_read` is the expected
permission for read-only ad-account access. The token is never written into a
campaign file or returned from status/report calls.

### Runtime policy

Meta performance sync requires external network access and therefore obeys:

```text
online                 allowed
restricted_network     requires meta-performance in the allowlist
offline                blocked
air_gapped             blocked
```

Read-only Insights access does **not** require `ADCLIP_ALLOW_LIVE_APIS=1`
because it is not a model-generation billing authorization. That flag remains
reserved for potentially paid generation providers.

## Workflow

### 1. Generate or import a campaign

The manifest will contain stable creative IDs.

### 2. Link a deployed Meta ad

```bash
adclip performance link-meta ./campaign \
  --variant-id v01 \
  --account-id act_123456 \
  --ad-id 987654321
```

Optional campaign, ad-set, creative, and ad-name IDs can be supplied at link
time. A later sync refreshes metadata from Meta.

### 3. Sync one exact measurement window

```bash
export ADCLIP_META_ACCESS_TOKEN=...

adclip performance sync-meta ./campaign \
  --since 2026-08-01 \
  --until 2026-08-07
```

The connector reads only linked ad IDs. It does not scan an account and does not
modify delivery state.

### 4. Inspect the latest or an exact window

```bash
adclip performance report ./campaign

adclip performance report ./campaign \
  --since 2026-08-01 \
  --until 2026-08-07
```

When no dates are supplied, adclip selects the latest exact stored window rather
than aggregating arbitrary overlapping observations.

### 5. Compare creatives descriptively

```bash
adclip performance compare ./campaign \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --metric ctr

adclip performance compare ./campaign \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --metric roas \
  --action-type purchase
```

Supported initial comparison metrics:

```text
ctr
outbound_ctr
cpc
cpm
impressions
clicks
action_rate
cost_per_action
roas
```

## Interpretation rules

The first learning layer is intentionally descriptive.

- Rankings do not claim causal lift.
- No LLM score is treated as conversion probability.
- Creatives should be compared over the same measurement window.
- Meta reach is not additive across ads; summaries expose it as
  `reported_reach_sum` and explicitly mark `reach_is_additive: false`.
- Action-rate, CPA, and ROAS comparisons require an explicit platform action
  type.
- Overlapping windows are stored but never silently summed by the default report.
- Attribution/reporting-time differences remain visible in each observation.

This keeps the evidence layer honest while experiment and uncertainty models
are built.

## MCP tools

```text
adclip_performance_link_meta
adclip_performance_deployments
adclip_performance_sync_meta
adclip_performance_report
adclip_performance_compare
```

The same application service powers CLI and MCP interfaces.

## Next steps

1. Move campaign/deployment/observation records into SQLite while preserving the
   portable JSON projection.
2. Add explicit experiment and hypothesis objects.
3. Add confidence intervals and minimum-evidence rules for rate comparisons.
4. Add fatigue analysis over non-overlapping time windows.
5. Add creative-attribute extraction and changed-factor lineage.
6. Add Google Ads and TikTok adapters against the same observation schema.
7. Add ESP/email performance observations.
8. Add a next-test planner that distinguishes evidence from hypothesis.
9. Only after the read/learning loop is trustworthy, add draft/paused activation
   with explicit human authorization.
