# DTC skincare product launch

**Business goal:** launch a daily moisturizer and drive first purchases.  
**Audience:** adults 25–40 shopping for a simple moisturizer for dry or sensitive skin.  
**Channels:** Meta Feed, Stories/Reels, TikTok, Google Search, and email.  
**Offer:** 20% off the first order.  
**Primary creative question:** does vivid problem framing outperform a plain product benefit?

This is the canonical adclip example because it looks like a normal performance-marketing campaign and touches most of the product surface without needing domain-specific explanation.

## What adclip demonstrates

```text
campaign brief
  -> cross-channel copy / static / short-form video
  -> launch email sequence
  -> exact creative lineage
  -> deployment observations
  -> hook experiment
  -> evidence-aware next test
```

Run the creative brief with deterministic providers:

```bash
adclip run examples/01-dtc-skincare/brief.json \
  --text-provider fake \
  --image-provider fake \
  --video-provider fake
```

Generate the launch email sequence without a paid API:

```bash
adclip email generate \
  examples/01-dtc-skincare/email_brief.json \
  --provider fake
```

The dedicated learning demo in [`../06-creative-experiment`](../06-creative-experiment/) uses the same product category and tests a concrete hook hypothesis against synthetic performance observations.

## Campaign strategy

The brief asks for several durable angles rather than one repeated message:

- ingredient-led simplicity;
- problem/solution framing;
- everyday lifestyle fit;
- first-order offer.

The campaign avoids medical or unsupported proof language so the example also shows how brand and claim constraints can travel with the brief.
