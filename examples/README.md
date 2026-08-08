# adclip examples

These examples are organized around marketing problems rather than internal subsystems. The goal is to let a marketer, agency, or growth team scan the repository and quickly recognize a campaign they might actually run.

Unless a section explicitly says otherwise, the examples can be exercised with fake providers or checked-in artifacts and without a live marketing account.

## Portfolio

| Example | Business problem | Channels / surface | What it demonstrates |
| --- | --- | --- | --- |
| [`01-dtc-skincare`](01-dtc-skincare/) | Product launch and first purchase | Meta, Reels, TikTok, Google, email | Canonical cross-channel campaign |
| [`02-b2b-saas-lead-gen`](02-b2b-saas-lead-gen/) | Qualified demo generation | LinkedIn, Google Search | B2B message adaptation |
| [`03-local-service-lead-gen`](03-local-service-lead-gen/) | Same-day local leads | Meta, Google Search | Direct-response/local agency work |
| [`04-subscription-winback`](04-subscription-winback/) | Reactivate lapsed subscribers | Email | Lifecycle retention and offers |
| [`05-mobile-app-acquisition`](05-mobile-app-acquisition/) | Free-trial acquisition | TikTok, Reels, Shorts, Meta | Short-form video routing |
| [`06-creative-experiment`](06-creative-experiment/) | Learn which hook works better | Synthetic Meta observations | Lineage, evidence, experiment, next test |

## Recommended starting point

Start with the DTC skincare launch:

```bash
adclip run examples/01-dtc-skincare/brief.json \
  --text-provider fake \
  --image-provider fake \
  --video-provider fake
```

Then render the matching checked-in launch email with no model call:

```bash
adclip email render \
  examples/01-dtc-skincare/email_brief.json \
  examples/01-dtc-skincare/email_message.json \
  --output-dir ./adclip_skincare_email_render
```

That gives one coherent business case across paid creative and owned email. The email brief can also be passed to sequence generation when a compatible text provider is configured.

## See the learning loop

The dedicated creative-testing example uses the same product category so the transition from creation to evidence feels continuous:

```bash
python examples/06-creative-experiment/build_demo.py
```

The builder creates exact control/treatment artifacts, synthetic deployment mappings, normalized observations, and one CTR hypothesis. It prints the experiment ID and commands for reporting, evaluation, and next-test recommendation.

The data is synthetic and deliberately favors the treatment. A `supported` result still keeps `causal_claim: false`; the example demonstrates adclip's evidence contract rather than pretending a fixture proves real-world causal lift.

## Other checked-in fixtures

The older flat files remain useful as lower-level examples and compatibility fixtures:

- `email_campaign_brief.json` — generic email-campaign schema example;
- `email_message.json` — one structured email message;
- `email_lint_context.json` — campaign-aware lint context;
- `email_patches.json` — stable block-targeted edits;
- `taichi_brief.json` — crypto policy/healing example.

They are not the primary marketer-facing onboarding path.

## Safety

Keep `ADCLIP_ALLOW_LIVE_APIS` unset when following the examples with fake providers.

The fake creative providers, email renderer/linter/editor, and synthetic creative-test demo make no paid model calls. `examples/06-creative-experiment/build_demo.py` does not contact Meta or any other external service.

See [`../docs/QUICKSTART.md`](../docs/QUICKSTART.md) for the guided walkthrough.
