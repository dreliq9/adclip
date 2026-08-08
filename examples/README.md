# adclip examples

These examples are intended to be runnable, inspectable demonstrations of the
current product surface. Unless a section explicitly says otherwise, they can be
used without paid APIs or live marketing accounts.

## Creative generation

### `portable_power_brief.json`

A neutral cross-channel campaign brief covering:

- Meta 4:5 static creative;
- Google responsive search ad copy;
- Stories/Reels short-form video;
- LinkedIn static creative.

Run it safely with deterministic providers:

```bash
adclip run examples/portable_power_brief.json \
  --text-provider fake \
  --image-provider fake \
  --video-provider fake
```

This is the recommended first campaign example because it exercises static,
text, and video paths in one run without a regulated-policy profile.

### `taichi_brief.json`

A smaller crypto-policy example retained for compatibility and policy testing.
It is useful when exercising `must_avoid`, policy profiles, healing, and judge
behavior. It is not the primary onboarding example.

## Email authoring

### `email_campaign_brief.json`

A complete structured email campaign brief. Generate a deterministic campaign:

```bash
adclip email generate examples/email_campaign_brief.json --provider fake
```

### `email_message.json`

A single structured message that can be rendered without any model call:

```bash
adclip email render \
  examples/email_campaign_brief.json \
  examples/email_message.json \
  --output-dir ./adclip_email_render
```

### `email_lint_context.json`

Campaign-aware context for HTML linting:

```bash
adclip email lint ./adclip_email_render/email.html \
  --context examples/email_lint_context.json \
  --plain-text ./adclip_email_render/email.txt
```

### `email_patches.json`

Block-targeted structural edits:

```bash
adclip email patch-message \
  examples/email_message.json \
  examples/email_patches.json \
  --output ./adclip_email_message_edited.json
```

## Performance and experiments

### `build_performance_demo.py`

Builds a complete synthetic campaign learning bundle locally:

```text
campaign + exact creative hashes
  -> deployment records
  -> normalized observations
  -> explicit hook experiment
  -> confidence-gated evaluation
  -> next-test recommendation
```

Run:

```bash
python examples/build_performance_demo.py
```

Then inspect the generated `./adclip_performance_demo` directory:

```bash
adclip performance report ./adclip_performance_demo \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion

adclip performance compare ./adclip_performance_demo \
  --since 2026-08-01 \
  --until 2026-08-07 \
  --action-report-time conversion \
  --metric ctr
```

The builder prints an `exp_...` ID. Use it for:

```bash
adclip performance experiment-evaluate ./adclip_performance_demo \
  --experiment-id exp_... \
  --since 2026-08-01 \
  --until 2026-08-07

adclip performance next-test ./adclip_performance_demo \
  --experiment-id exp_... \
  --since 2026-08-01 \
  --until 2026-08-07
```

The data is synthetic and deliberately favors the treatment. A supported
hypothesis is still returned with `causal_claim: false` because this example is
about evidence mechanics, not proof of real-world causality.

## Safety

For local examples, leave this unset:

```text
ADCLIP_ALLOW_LIVE_APIS
```

The fake providers, email renderer/linter/editor, and synthetic performance demo
make no paid model calls. `build_performance_demo.py` does not contact Meta or
any other external service.

See [`../docs/QUICKSTART.md`](../docs/QUICKSTART.md) for the guided path through
these examples.
