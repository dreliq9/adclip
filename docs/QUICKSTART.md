# Quickstart

This quickstart exercises the current repository without paid model calls or a
live ad account. It covers creative generation, email rendering, and the
performance/experiment loop.

## 1. Install the current repository

The packaged PyPI release may lag `main`, so use a source checkout when you want
the exact feature set documented in this repository.

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

## 2. Run a zero-cost cross-channel creative campaign

The portable-power example includes static, text, and short-form-video formats.
All providers are deterministic fakes, so this makes no network or paid API
calls.

```bash
adclip run examples/portable_power_brief.json \
  --text-provider fake \
  --image-provider fake \
  --video-provider fake
```

The output directory from the brief contains the campaign brief, generated
variants, and a manifest with stable campaign/creative lineage and model
provenance.

Inspect it through MCP with `adclip_campaign_status`, or directly on disk.

## 3. Explore task-oriented model routing

Routes describe the marketing job rather than hard-coding a model name:

```bash
adclip routes --modality image
adclip route-recommend image --text-heavy
adclip route-recommend image --brand-control
adclip routes --modality video
adclip route-recommend video --multi-shot
```

A route selects a current primary provider/model/options tuple. Explicit
provider/model arguments still override the route.

## 4. Exercise email locally

Render the checked-in structured email message with no model call:

```bash
adclip email render \
  examples/email_campaign_brief.json \
  examples/email_message.json \
  --output-dir ./adclip_email_render
```

Lint it:

```bash
adclip email lint ./adclip_email_render/email.html \
  --context examples/email_lint_context.json \
  --plain-text ./adclip_email_render/email.txt
```

Patch the structured message:

```bash
adclip email patch-message \
  examples/email_message.json \
  examples/email_patches.json \
  --output ./adclip_email_message_edited.json
```

Generate an entire sequence with the fake text provider:

```bash
adclip email generate examples/email_campaign_brief.json --provider fake
```

Email delivery is deliberately outside this native authoring slice. The output
is portable HTML/text/header/message state for a future ESP connector.

## 5. Build a complete synthetic performance demo

The demo builder creates two exact creative artifacts, deployment mappings,
normalized Meta-shaped observations, and an explicit hook experiment. It makes
no network calls and uses no credentials.

```bash
python examples/build_performance_demo.py
```

By default it writes `./adclip_performance_demo` and prints the experiment ID.

Report the synthetic window:

```bash
adclip performance report ./adclip_performance_demo \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion
```

Compare CTR descriptively:

```bash
adclip performance compare ./adclip_performance_demo \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion \
  --metric ctr
```

Evaluate the experiment using the `exp_...` ID printed by the builder:

```bash
adclip performance experiment-evaluate ./adclip_performance_demo \
  --experiment-id exp_... \
  --since 2026-08-01 \
  --until 2026-08-07
```

Then ask for the next controlled action:

```bash
adclip performance next-test ./adclip_performance_demo \
  --experiment-id exp_... \
  --since 2026-08-01 \
  --until 2026-08-07
```

The synthetic treatment is deliberately stronger on CTR, so this example should
produce a supported directional hypothesis while still returning
`causal_claim: false`.

## 6. Connect read-only Meta performance when ready

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

The current connector implements reads only. It does not create, edit, pause,
resume, target, or budget campaigns/ads.

## 7. Opt into real generation only when intended

Potentially paid generation remains gated:

```bash
export ADCLIP_ALLOW_LIVE_APIS=1
```

Use `adclip estimate` before generation and prefer explicit task routes. Keep the
gate unset for examples, tests, and routine local validation.

## Where to go next

- Model setup: [`MODEL_PROVIDERS.md`](MODEL_PROVIDERS.md)
- Image/video routes: [`MODEL_ROUTING.md`](MODEL_ROUTING.md)
- Email: [`EMAIL_CAMPAIGNS.md`](EMAIL_CAMPAIGNS.md)
- Performance: [`PERFORMANCE_LEARNING.md`](PERFORMANCE_LEARNING.md)
- Experiment evidence: [`EXPERIMENTS.md`](EXPERIMENTS.md)
- Architecture/roadmap: [`STANDALONE_ARCHITECTURE.md`](STANDALONE_ARCHITECTURE.md)
