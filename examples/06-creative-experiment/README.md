# Creative experiment: problem framing vs plain benefit

**Business goal:** improve paid-social click-through rate for a moisturizer launch.  
**Hypothesis:** a vivid problem-framing hook will outperform a plain product-benefit hook.  
**Changed factor:** opening hook only.  
**Primary metric:** CTR.  
**Evidence:** synthetic, offline, deliberately constructed for product demonstration.

This is the example that shows what makes adclip more than a generator.

```text
hypothesis
  -> exact control/treatment artifacts
  -> stable creative IDs + hashes
  -> synthetic deployment observations
  -> minimum evidence
  -> confidence interval
  -> supported / contradicted / inconclusive
  -> next-test recommendation
```

Build the fixture:

```bash
python examples/06-creative-experiment/build_demo.py
```

The script prints the generated campaign directory and experiment ID. It makes no network requests and uses no credentials.

Then run the printed commands, or manually inspect the synthetic window:

```bash
adclip performance report ./adclip_creative_test_demo \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion

adclip performance compare ./adclip_creative_test_demo \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion \
  --metric ctr
```

The treatment is intentionally stronger so the example reaches a `supported` directional verdict. The evaluation still returns `causal_claim: false`: the fixture demonstrates adclip's evidence contract, not a claim that synthetic or observational data proves real-world causal lift.
