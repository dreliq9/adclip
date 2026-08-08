# Quickstart

This quickstart exercises the current repository without paid model calls or a live ad account. It follows one recognizable DTC skincare campaign from cross-channel creative into email and then into a synthetic creative experiment.

## 1. Install the current repository

The packaged PyPI release may lag `main`, so use a source checkout when you want the exact feature set documented in this repository.

```bash
git clone https://github.com/dreliq9/adclip.git
cd adclip
python3.11 -m venv .venv
```

macOS/Linux:

```bash
.venv/bin/pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
.venv\Scripts\python -m pip install -e ".[dev]"
```

Check the runtime:

```bash
adclip status
adclip formats
adclip routes
```

## 2. Run a zero-cost DTC product-launch campaign

The canonical example launches a fictional daily moisturizer across Meta Feed, Stories/Reels, TikTok, and Google Search. All providers below are deterministic fakes, so this makes no network or paid API calls.

```bash
adclip run examples/01-dtc-skincare/brief.json \
  --text-provider fake \
  --image-provider fake \
  --video-provider fake
```

The output directory from the brief contains campaign state, generated variants, and a manifest with stable campaign/creative lineage and model provenance.

The campaign is intentionally ordinary: a first-order offer, several creative angles, and explicit claim constraints. That makes it useful as a product walkthrough rather than a niche domain demo.

## 3. Explore task-oriented model routing

Routes describe the marketing job rather than hard-coding a model name:

```bash
adclip routes --modality image
adclip route-recommend image --text-heavy
adclip route-recommend image --brand-control
adclip routes --modality video
adclip route-recommend video --multi-shot
```

A route selects a current primary provider/model/options tuple. Explicit provider/model arguments still override the route.

## 4. Render the matching launch email locally

The skincare example includes a structured campaign brief and one checked-in launch message. Rendering requires no model call:

```bash
adclip email render \
  examples/01-dtc-skincare/email_brief.json \
  examples/01-dtc-skincare/email_message.json \
  --output-dir ./adclip_skincare_email_render
```

The output contains responsive HTML, plain text, headers, and lint metadata.

For lower-level editing examples, the generic checked-in fixtures still support:

```bash
adclip email patch-message \
  examples/email_message.json \
  examples/email_patches.json \
  --output ./adclip_email_message_edited.json
```

`email_brief.json` is also ready for provider-neutral sequence generation when a compatible text provider is configured. The generic `fake` text provider is intentionally a copy-generation fixture, not an email-sequence generator.

## 5. Build a complete synthetic creative experiment

The experiment example stays in the same skincare category. It creates two exact Meta-feed creative artifacts that differ in their opening hook, synthetic deployment mappings, normalized observations, and an explicit CTR hypothesis.

```bash
python examples/06-creative-experiment/build_demo.py
```

By default it writes `./adclip_creative_test_demo` and prints the experiment ID.

Report the synthetic window:

```bash
adclip performance report ./adclip_creative_test_demo \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion
```

Compare CTR descriptively:

```bash
adclip performance compare ./adclip_creative_test_demo \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion \
  --metric ctr
```

Evaluate the experiment using the `exp_...` ID printed by the builder:

```bash
adclip performance experiment-evaluate ./adclip_creative_test_demo \
  --experiment-id exp_... \
  --since 2026-08-01 \
  --until 2026-08-07
```

Then ask for the next controlled action:

```bash
adclip performance next-test ./adclip_creative_test_demo \
  --experiment-id exp_... \
  --since 2026-08-01 \
  --until 2026-08-07
```

The synthetic control runs at 2.7% CTR and the treatment at 4.4%, so the fixture is deliberately strong enough to demonstrate a `supported` directional hypothesis. It still returns `causal_claim: false`.

## 6. Explore other common marketing workloads

The remaining examples are smaller on purpose:

```text
02-b2b-saas-lead-gen       LinkedIn + Google demo generation
03-local-service-lead-gen  Meta + Search local direct response
04-subscription-winback    email lifecycle retention
05-mobile-app-acquisition  TikTok/Reels/Shorts acquisition
```

See [`../examples/README.md`](../examples/README.md) for the marketer-facing summary of each case.

## 7. Connect read-only Meta performance when ready

Linking is local only:

```bash
adclip performance link-meta ./your_campaign \
  --variant-id v01 \
  --account-id act_123456 \
  --ad-id 987654321
```

Then configure a read-capable Meta token and sync an exact attribution window:

```bash
export ADCLIP_META_ACCESS_TOKEN=...

adclip performance sync-meta ./your_campaign \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion
```

The current connector implements reads only. It does not create, edit, pause, resume, target, or budget campaigns/ads.

## 8. Opt into real generation only when intended

Potentially paid generation remains gated:

```bash
export ADCLIP_ALLOW_LIVE_APIS=1
```

Use `adclip estimate` before generation and prefer explicit task routes. Keep the gate unset for examples, tests, and routine local validation.

## Where to go next

- Example portfolio: [`../examples/README.md`](../examples/README.md)
- Model setup: [`MODEL_PROVIDERS.md`](MODEL_PROVIDERS.md)
- Image/video routes: [`MODEL_ROUTING.md`](MODEL_ROUTING.md)
- Email: [`EMAIL_CAMPAIGNS.md`](EMAIL_CAMPAIGNS.md)
- Performance: [`PERFORMANCE_LEARNING.md`](PERFORMANCE_LEARNING.md)
- Experiment evidence: [`EXPERIMENTS.md`](EXPERIMENTS.md)
- Architecture/roadmap: [`STANDALONE_ARCHITECTURE.md`](STANDALONE_ARCHITECTURE.md)
