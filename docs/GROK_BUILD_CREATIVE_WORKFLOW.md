# Grok Build creative workflow

**Status:** Active operator guide  
**Audience:** Agents and humans running adclip campaigns **inside Grok Build**  
**Complementary to:** native `adclip run` routes ([MODEL_ROUTING](MODEL_ROUTING.md), [MODEL_PROVIDERS](MODEL_PROVIDERS.md))

This document describes a **Grok Build–specific** path for producing shippable
static (and optional video) ad creatives when:

- product photography already exists (brand CDN / studio shots);
- exact headlines, specs, and CTAs must be correct;
- lifestyle / field context is needed beyond deterministic fake media;
- fal / OpenAI image keys or `ADCLIP_ALLOW_LIVE_APIS` are unavailable or undesirable.

It does **not** replace the adclip CLI pipeline. It is an **agent-side creative
loop** that still lands artifacts in an adclip-shaped campaign directory
(manifest, variants, copy, media brief).

---

## When to use which path

| Path | Use when |
| --- | --- |
| **`adclip run`** (fal / OpenAI / fake) | Full automated pool → policy → score → media; live APIs configured |
| **`adclip regenerate`** | One variant needs copy and/or visual redo *inside* an adclip-generated campaign |
| **Grok Build workflow (this doc)** | Official product refs + Imagine scene plates + **code typography**; review–regen by variant |

Hybrid is normal: brief and RSA from adclip or hand-authored JSON; plates from
Imagine; type from a local compositor script; inventory still uses
`manifest.json` + `variants/vNN/`.

---

## Product thesis (Grok Build)

```text
Official product photography
  -> Imagine scene plates (product-in-context, no ad text)
  -> Code-composited typography (exact headlines / specs / CTAs)
  -> Scorecard review per variant
  -> Targeted regen (plate | type | both)
  -> Re-review only changed IDs
  -> Lock winners in manifest + media brief
```

**Hard rule:** do not ask diffusion models to render final ad copy. Specs,
prices, URLs, and legal claims go through code (Pillow/HTML) so they stay
correct. See the Grok Build `imagine` skill: exact text is a code job.

---

## Tools available in Grok Build

| Capability | Tool | Role in this workflow |
| --- | --- | --- |
| New scene without product ref | `image_gen` | Backgrounds only (prefer product-ref edits when fidelity matters) |
| Product-in-scene | `image_edit` | **Primary** — official studio JPG as reference |
| Short social video | `image_to_video` | Animate a locked plate (may fail under ZDR without `upload_url`) |
| Exact type overlay | Local Python (Pillow) | Final PNG sizes per channel |
| Campaign structure | adclip brief / manifest conventions | `variants/`, `copy.json`, `manifest.json` |

Native adclip media providers (`fal`, `openai`, `fake`) remain available via
CLI when keys and `ADCLIP_ALLOW_LIVE_APIS=1` are set. This workflow is the
fallback and the quality path for reference-locked product ads.

---

## Recommended campaign layout

Store Grok Build campaigns under the adclip checkout (example):

```text
campaigns/<brand-or-product>/
  brief.json                 # optional AdBrief for adclip estimate/copy
  README.md
  assets/
    <official studio shots>.jpg
    cutouts/                 # optional transparent products
    imagine/                 # scene plates from image_edit
      plate_<angle>.jpg
      plate_<angle>_rN.jpg   # archived prior plates
  build_imagine_ads.py       # plate + type compositor (channel sizes)
  recompose_vNN.py           # optional single-variant recompose helpers
  output/
    manifest.json
    media_brief.json
    CREATIVE_REVIEW.md       # living scorecard
    variants/
      v01/
        <format>.png
        copy.json
        plate_<name>.jpg     # plate used for this ship
      v02/
      ...
```

### Naming discipline

- **Variant IDs** (`v01`…`vNN`) are stable handles for review and regen.
- Always identify work by **path + format + headline**, not memory:
  `output/variants/v03/google_display_landscape.png`.
- When the user says “5” or “6”, **list the inventory** before regenerating.
  Mis-targeted regens waste plate history (documented failure mode below).

---

## Phase 0 — Brief and claim guardrails

Author or reuse an `AdBrief`-compatible brief:

- product, value prop, audience, angles, tone, CTA;
- formats (Meta, GDN, LinkedIn, X, Stories, RSA, …);
- `must_include` / `must_avoid` (stock status, overclaims, regulated language);
- sales/ops constraints (e.g. DTC paused → awareness CTAs only).

Channel char limits still apply (see `adclip formats`).

---

## Phase 1 — Product references

1. Download **official** product photography (brand CDN / site).
2. Prefer front-facing studio shots for hero recognition.
3. Optionally cut out white studio backgrounds for compositing.
4. Note **physical truth** for the product (used in review):
   - connector types and **where** cables attach (e.g. solar via rear EC8 + adapter, not MC4 on the front);
   - which LCDs should be lit;
   - modular stack / branding positions.

Imagine will invent plausible-but-wrong cables. The review rubric must catch that.

---

## Phase 2 — Scene plates (Imagine)

For each creative angle, run `image_edit` with:

1. **One strong product reference** (front studio preferred).
2. A prompt that:
   - places **this exact product** in a concrete scene;
   - preserves color, modular form, ports, handle;
   - requests **no text, badges, watermarks, or UI overlays**;
   - states cable policy explicitly when needed:
     *empty outlets, capped DC ports, no MC4s, no phantom side leads*.
3. Target aspect ratio when multi-ref allows; single-image edit often **preserves source aspect** — plan to **smart-crop** in the compositor.

Save plates under `assets/imagine/plate_<angle>.jpg`.

### Plate prompt checklist

- [ ] Product identity locked to reference  
- [ ] Scene matches angle (cold, outage, field, hero, …)  
- [ ] No ad copy in the render  
- [ ] Cable / connector policy stated  
- [ ] Room for type (negative space or intentional dark zone)  
- [ ] Front face visible for recognition (unless rear view is intentional)

---

## Phase 3 — Code typography (final ads)

Compose channel-sized finals with Pillow (or HTML → raster):

| Format | Typical size |
| --- | --- |
| `meta_feed_1x1` | 1080×1080 |
| `meta_feed_4x5` | 1080×1350 |
| `google_display_landscape` | 1200×628 |
| `linkedin_single` | 1200×627 |
| `x_promoted` | 1200×675 |
| `stories_reels_9x16` | 1080×1920 |
| `google_rsa` | text JSON only (no plate) |

Compositor responsibilities:

1. Smart-cover crop plate to size (bias `center` / `left` / `right` / `top`).
2. Scrim for legibility (`left` panel or `bottom` gradient).
3. Exact brand, eyebrow, headline, body, CTA pill, URL.
4. Write `variants/vNN/<format>.png` + `copy.json` (headline, body, CTA, primary_text, plate name, landing URL).
5. Update `manifest.json` hashes and `media_brief.json` for media buyers.

Keep compositor logic in-repo under the campaign folder (e.g.
`build_imagine_ads.py`) so regen is reproducible.

---

## Phase 4 — Review–regenerate loop (required)

Do **not** ship a first Imagine batch without a scorecard. First batches fail on
product fidelity, type collision, and wrong-angle views.

### 4.1 Inventory

Print for every variant:

```text
id | format | file name | headline | plate | path
```

### 4.2 Scorecard rubric (1–10 or pass/fail)

| Dimension | Question |
| --- | --- |
| **Product fidelity** | Recognizable as the real SKU? LCDs, ports, color, modular stack correct? |
| **Scene fit** | Does the environment sell the angle? |
| **Type / contrast** | Readable? Safe margins? Not sitting on critical product features? |
| **Claim safety** | Aligns with brief `must_avoid` / sales status? |
| **Platform fit** | Size, crop, CTA, RSA length limits? |
| **Engineering truth** | Cables, connectors, orientations physically plausible for this product? |

### 4.3 Verdicts

| Verdict | Meaning | Action |
| --- | --- | --- |
| `SHIP` | Good enough to lock | No change |
| `REGEN_PLATE` | Scene or product image wrong | New `image_edit`; archive old plate as `*_rN.jpg` |
| `REGEN_TYPE` | Plate OK; type/layout wrong | Recompose only (fast) |
| `REGEN_PLATE + TYPE` | Both | New plate then recompose |
| `KILL` | Angle or format not useful | Drop from ship set; note in review |

Write results to `output/CREATIVE_REVIEW.md` (append rounds; do not overwrite history).

After a set is largely `SHIP` (or before first spend), run a **performance
creative audit** with the fill-in template in
[CREATIVE_AUDIT_TEMPLATE.md](CREATIVE_AUDIT_TEMPLATE.md). Save as
`output/CREATIVE_AUDIT.md` under the local campaign folder. That audit ranks
variants for cold traffic vs secondary roles and defines a test plan; the
review scorecard above is for **production quality**, the audit is for
**performance priority**.

### 4.4 Targeted regen only

Regenerate **only** non-SHIP IDs. Confirm path with the user when ambiguous:

```text
User: "fix 6" / "the cabling one"
Agent: list inventory → confirm path → then regen that ID only
```

### 4.5 Re-review changed IDs

Score only regenerated variants. Update scorecard + manifest `review_round` /
`regen` notes. Lock the set when all remaining are `SHIP`.

### 4.6 Archive plates

Before overwriting a plate:

```text
plate_overland.jpg  ->  plate_overland_r1.jpg
```

Never delete prior plates until the campaign is closed; mis-targeted regens
need rollback.

---

## Phase 5 — Optional video

1. Lock a still plate (prefer 9:16 for Stories/Reels).
2. `image_to_video` with a **simple** motion (slow push-in; product stable).
3. If the environment returns ZDR / `upload_url` errors, document and ship stills;
   do not block the campaign on video.

---

## Engineering fidelity (product-specific rules)

Generalize these checks for every hardware / physical product campaign:

1. **Connector map** — document real ports before Imagine runs.  
2. **No phantom cables** — models invent solar leads, side exits, and front charge cords.  
3. **Prefer empty ports** for hero ads unless a real accessory is intentional and accurate.  
4. **Front face for awareness** — rear/side-only views fail product recognition.  
5. **Lit UI** — blank LCDs look broken vs real powered product shots.  
6. **Color** — golden-hour warm shift is OK; wrong product color family is not.

Example failure: accessory connectors shown on the wrong face of a device, or
cables “exiting” a panel that has no such port on the real SKU → `REGEN_PLATE`
with an explicit no-cable / empty-port policy.

---

## Relationship to adclip `regenerate`

| | adclip `regenerate` | Grok Build loop |
| --- | --- | --- |
| Entry | MCP/CLI on campaign dir | Agent + Imagine + local scripts |
| Copy | LLM pool + policy | Hand / curated / LLM, stored in `copy.json` |
| Visual | fal/OpenAI/`fake` via image_fn | `image_edit` plates + Pillow |
| Unit of work | one variant `what=copy|visual|both` | same idea: plate / type / both |
| Review | optional human | **required scorecard** (this doc) |

When live adclip media is configured, prefer `adclip regenerate` for
in-pipeline variants. When plates came from Imagine, **do not** expect
`adclip regenerate --what visual` to call Imagine; re-run this workflow’s
plate + recompose steps instead.

---

## Operator checklist (copy/paste for agents)

```text
[ ] Brief + claim guardrails written
[ ] Official product refs downloaded
[ ] Physical connector/UI notes written
[ ] Plates generated (no ad text in renders)
[ ] Finals composited with exact type per format
[ ] Inventory table printed (id | format | headline | path)
[ ] CREATIVE_REVIEW.md scorecard filled
[ ] Non-SHIP only regenerated; plates archived *_rN
[ ] Re-review of changed IDs only
[ ] manifest.json + media_brief.json updated
[ ] User confirmed ambiguous IDs by full path before regen
```

---

## Local client campaigns (gitignored)

Brand-specific work (product photos, plates, briefs, compositor scripts, finals)
lives under **`campaigns/<client-or-product>/`**, which is **gitignored**. Do not
commit client assets, Imagine plates, or rendered ads.

Typical local tree (not in git):

```text
campaigns/<client-or-product>/
  assets/           # official photography + imagine/
  build_*.py        # compositor
  output/
    CREATIVE_REVIEW.md
    manifest.json
    variants/v01/…
```

### Failure modes this loop is designed to catch

| Failure | Fix |
| --- | --- |
| Placeholder silhouettes / fake copy | Real product refs + Imagine plates + code type |
| Blank device UI / type on product face | `REGEN_PLATE` + `REGEN_TYPE` |
| Rear-only product (unrecognizable) | `REGEN_PLATE` front-facing |
| Wrong connectors / phantom cables | `REGEN_PLATE` with empty-port / no-cable policy |
| Mis-targeted regen (“fix 6”) | Re-list inventory; confirm full path before regen |

---

## What this workflow deliberately does not do

- Create live Meta/Google ads (adclip performance connectors are read-oriented).
- Guarantee Imagine preserves millimeter-perfect product CAD.
- Replace bake-offs or route selection for fal/OpenAI models.
- Silent multi-provider fallbacks (same cost discipline as adclip core).

---

## See also

- [STANDALONE_ARCHITECTURE.md](STANDALONE_ARCHITECTURE.md) — product loop and boundaries  
- [MODEL_PROVIDERS.md](MODEL_PROVIDERS.md) — adclip text/image/video providers  
- [MODEL_ROUTING.md](MODEL_ROUTING.md) — task routes vs explicit overrides  
- [CREATIVE_AUDIT_TEMPLATE.md](CREATIVE_AUDIT_TEMPLATE.md) — pre-spend creative audit  
- [PERFORMANCE_LEARNING.md](PERFORMANCE_LEARNING.md) — post-ship measurement  
- [EXPERIMENTS.md](EXPERIMENTS.md) — creative experiment evidence  
