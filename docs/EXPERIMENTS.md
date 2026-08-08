# Creative Experiment and Next-Test Contract

**Status:** Active experimental foundation  
**Date:** 2026-08-07

## Purpose

adclip should learn from marketing performance without pretending that every
observed winner proves a causal effect. This layer records hypotheses before
interpretation, snapshots the exact creative artifacts being compared, applies
minimum-evidence rules, and separates inferential rate evidence from descriptive
value metrics.

```text
hypothesis
  -> declared changed factor
  -> exact control/treatment creative IDs + artifact hashes
  -> matched observation window
  -> minimum evidence
  -> confidence interval where justified
  -> supported | contradicted | inconclusive
  -> next-test recommendation
```

## Experiment record

Experiments are stored in:

```text
campaign/performance/experiments.json
```

Each experiment records:

```text
exp_... experiment ID
cmp_... campaign ID
hypothesis statement
changed factor
control creative + variant + artifact SHA-256 + factor value
treatment creative + variant + artifact SHA-256 + factor value
primary metric
action type when required
expected direction
experiment design
minimum denominator/events per arm
confidence level
status
```

The two arms snapshot `creative_id` and `artifact_sha256`. If a variant is
regenerated later, that replacement artifact receives a different creative ID
and cannot silently inherit the experiment evidence.

The deterministic experiment ID also includes both declared factor values. The
same creative pair, factor name, metric, and action type can therefore be
re-declared with different factor values without silently overwriting the
previous experiment.

## Designs

### `controlled_single_factor`

Use when the team intentionally changed one declared creative factor. The
current implementation requires matching output formats so a placement-format
change cannot accidentally masquerade as a hook, offer, proof, or visual test.

This is still a **declared** single-factor design. adclip does not yet prove that
all other creative attributes or delivery conditions were identical or
randomized.

### `observational_comparison`

Use when the two creatives were not intentionally isolated as one changed
factor. The output is always descriptive. Even if a rate confidence interval
excludes zero, this design returns:

```text
descriptive_only: true
inferential: false
verdict: inconclusive
reason: observational_comparison_is_descriptive_only
causal_claim: false
```

Intervals may still be attached for inspection. The next-test planner responds
with `improve_measurement_design` rather than promoting an observational winner.

## Primary metrics

Initial experiment metrics:

```text
ctr
outbound_ctr
action_rate
cost_per_action
roas
```

`action_rate` is defined as:

```text
actions[action_type] / clicks
```

The descriptive reporting layer also exposes impression-normalized action rates
separately. `action_type` is required for action rate, CPA, and ROAS.

## Inferential boundary

Confidence intervals are currently produced only for controlled rate metrics
whose numerator and denominator are available from aggregate observations:

```text
CTR            clicks / impressions
outbound CTR   outbound clicks / impressions
action rate    actions / clicks
```

Each arm receives a Wilson proportion interval. The difference interval uses a
conservative Newcombe-style Wilson bound construction:

```text
treatment Wilson lower - control Wilson upper
...
treatment Wilson upper - control Wilson lower
```

A hypothesis can receive `supported` or `contradicted` only after both arms meet
the declared denominator and event thresholds. If a selected action count is
greater than clicks, adclip refuses binomial action-rate inference instead of
clamping the rate into a valid-looking interval.

For an expected increase:

```text
difference interval entirely > 0   -> supported
difference interval entirely < 0   -> contradicted
otherwise                           -> inconclusive
```

The signs reverse when lower is the expected direction.

## Measurement context

Experiment arms must use compatible platform and `action_report_time` values.
The performance layer treats the exact measurement window as:

```text
(since, until, action_report_time)
```

Different attribution reporting modes must not be added together. Report and
compare surfaces expose an explicit `action_report_time` selector when the same
dates have multiple stored modes.

## Value metrics remain descriptive

CPA and ROAS are useful point estimates, but aggregate campaign totals do not
provide enough variance information for a responsible confidence interval.
Therefore this first layer always returns:

```text
inferential: false
verdict: inconclusive
reason: value_metric_requires_variance_or_event_level_evidence
```

The direction remains visible. A later event-level or variance-aware ingestion
layer can promote these metrics to inferential tests.

## Causal claims

This foundation always emits:

```text
causal_claim: false
```

Even a declared single-factor creative test may still have delivery, audience,
auction, attribution, timing, or placement confounding. Future support for
verified randomized assignment can introduce a stronger causal contract, but it
must be explicit rather than inferred from two ad IDs.

## CLI workflow

### 1. Declare the experiment

```bash
adclip performance experiment-create ./campaign \
  --name "Contrarian hook CTR" \
  --hypothesis "A contrarian hook increases CTR" \
  --changed-factor hook \
  --control-variant v01 \
  --treatment-variant v02 \
  --control-value "plain benefit" \
  --treatment-value "contrarian challenge" \
  --metric ctr \
  --expected-direction higher
```

For action metrics:

```bash
adclip performance experiment-create ./campaign \
  --name "Proof purchase-rate test" \
  --hypothesis "Specific proof increases purchase rate after click" \
  --changed-factor proof \
  --control-variant v01 \
  --treatment-variant v02 \
  --control-value "generic proof" \
  --treatment-value "specific quantified proof" \
  --metric action_rate \
  --action-type purchase
```

Thresholds can be overridden explicitly:

```text
--min-denominator
--min-events
--confidence
```

Defaults are metric-aware. CTR/outbound CTR default to 1,000 denominator
observations and 20 events per arm. Action rate defaults to 100 clicks and 10
actions per arm.

### 2. Sync an exact platform window

```bash
adclip performance sync-meta ./campaign \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion
```

### 3. Evaluate

```bash
adclip performance experiment-evaluate ./campaign \
  --experiment-id exp_... \
  --since 2026-08-01 \
  --until 2026-08-07
```

If both attribution modes were synced for the same creative/date pair, the
current experiment evaluator refuses the incompatible measurement context rather
than combining them. A future experiment CLI selector may make that choice more
convenient; today the stored experiment evidence must be unambiguous.

### 4. Ask for the next test

```bash
adclip performance next-test ./campaign \
  --experiment-id exp_... \
  --since 2026-08-01 \
  --until 2026-08-07
```

The deterministic planner can return:

```text
replicate_supported_factor
revise_changed_factor
collect_more_evidence
improve_measurement_design
replicate_or_extend
```

When the interval crosses zero despite meeting the minimum threshold, it
recommends replication/extension rather than declaring a winner.

## MCP tools

```text
adclip_experiment_create
adclip_experiments
adclip_experiment_evaluate
adclip_experiment_next_test
```

These use the same application service and file-backed experiment records as the
CLI.

## Next steps

1. Verified randomized-assignment metadata and stronger causal semantics.
2. Multiple-comparison controls for experiments with more than one primary
   hypothesis.
3. Event-level or variance-aware CPA/ROAS inference.
4. Non-overlapping longitudinal windows for fatigue/change-point analysis.
5. Automatic creative-attribute extraction to audit whether a declared
   single-factor test actually changed only that factor.
6. Experiment-aware generation that creates treatment variants from a control
   while locking all non-tested factors.
7. Optional abductive next-test planning after the deterministic evidence layer
   establishes what is supported, contradicted, or unknown.
