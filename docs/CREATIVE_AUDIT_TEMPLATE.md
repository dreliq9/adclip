# Creative audit template

**Purpose:** Score a finished variant set against performance-creative criteria
before spend or scale. Complements the production scorecard in
[GROK_BUILD_CREATIVE_WORKFLOW.md](GROK_BUILD_CREATIVE_WORKFLOW.md)
(`SHIP` / `REGEN_PLATE` / `REGEN_TYPE` / `KILL`).

**When to run:** After plates + type are locked (or after a major regen round);
before allocating test budget; when diagnosing weak CTR/hook rate.

**Where to save:** Campaign-local only, e.g.
`campaigns/<name>/output/CREATIVE_AUDIT.md` (under gitignored `campaigns/`).

Copy everything below the line into that file and fill it in.

---

# Creative audit — `<campaign name>`

**Date:** YYYY-MM-DD  
**Auditor:**  
**Funnel assumption:** e.g. cold awareness → product page / lead / purchase  
**Offer / sales constraints:** e.g. in stock · DTC paused · waitlist only  
**Landing URL:**  
**Primary KPI for this test:** e.g. CTR · hook rate (3s) · CPC · CPA · ROAS  

## Scoring guide

| Score | Meaning |
| --- | --- |
| 1–3 | Broken / do not ship |
| 4–5 | Weak; fix before spend |
| 6–7 | Acceptable ship / secondary role |
| 8–9 | Strong for intended funnel stage |
| 10 | Exceptional (rare) |

| Code | Dimension | Question |
| --- | --- | --- |
| **H** | Hook / stop | Would the first frame + headline stop a cold scroller (or match search intent for RSA)? |
| **C** | Clarity | One idea? Product + benefit scannable in &lt;2s? |
| **P** | Product truth | Real SKU fidelity? Connectors/UI/cables plausible? |
| **F** | Funnel fit | CTA and promise match stage + offer constraints? |
| **Pl** | Platform fit | Aspect ratio, safe zones, length limits, channel norms? |

**Verdict labels (optional, map to workflow):**  
`PRIORITY_TEST` · `SHIP` · `SHIP_NIT` · `REGEN_TYPE` · `REGEN_PLATE` · `KILL`

---

## 1. Inventory

| ID | Format | Path | Angle | Headline (or RSA summary) | Plate / source |
| --- | --- | --- | --- | --- | --- |
| v01 | | `variants/v01/…` | | | |
| v02 | | | | | |
| v03 | | | | | |

---

## 2. Scoreboard

| ID | Format | Angle | H | C | P | F | Pl | **Avg** | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v01 | | | | | | | | | |
| v02 | | | | | | | | | |
| v03 | | | | | | | | | |

Sort by **Avg** (or by Priority Test first) when summarizing for stakeholders.

---

## 3. Per-variant notes

### v01 — `<format>` · `<headline>` · **avg**

| Dim | Score | Note |
| --- | --- | --- |
| H | | |
| C | | |
| P | | |
| F | | |
| Pl | | |

**Role:** cold opener / retarget / display filler / search / kill  
**Gaps / next action:**  

<!-- Repeat block per variant -->

---

## 4. Set-level checklist

| Criterion | Status (Pass / Partial / Fail) | Notes |
| --- | --- | --- |
| One idea per ad | | |
| Distinct angles (not duplicate messages) | | |
| Hook strength for cold traffic (if cold) | | |
| Clarity over cleverness | | |
| Placement-native sizes / crops | | |
| Proof present when claim is non-obvious | | |
| CTA matches funnel + offer state | | |
| Product / brand truth | | |
| Claim safety (`must_avoid`, policy) | | |
| Test matrix (angle × hook × format) | | |
| Fatigue / refresh plan | | |
| Landing page continues the ad promise | | |

---

## 5. Ranked ship list

| Rank | ID | Primary use |
| --- | --- | --- |
| 1 | | |
| 2 | | |
| 3 | | |

---

## 6. Recommended test plan

### Tier 1 — first spend (cold / primary objective)

1.  
2.  
3.  

**Control:**  
**Hypothesis:**  

### Tier 2 — channel coverage

-  

### Tier 3 — produce before scale

| Priority | Item | Action |
| --- | --- | --- |
| P1 | | |
| P2 | | |
| P3 | | |

### Do not prioritize yet

-  

---

## 7. Hook / angle matrix (optional)

Use when the set has formats but not enough **within-angle** diversity.

| Angle | Hook A (shipped) | Hook B (todo) | Hook C (todo) | Formats covered |
| --- | --- | --- | --- | --- |
| | | | | |
| | | | | |

Highest leverage is usually **new hooks on winning angles**, not new formats.

---

## 8. Bottom line

**What is strong:**  

**What is weak:**  

**Single highest-leverage next step:**  

---

## Appendix A — Dimension rubrics (reference)

### Hook (H)

| Score | Social / video-static | Search RSA |
| --- | --- | --- |
| 9–10 | Specific number, pattern interrupt, or story in frame one | Headlines cover brand + benefit + feature intents |
| 7–8 | Clear benefit, solid visual | Good coverage, some thin lines |
| 5–6 | Pretty but generic category look | Vague or repetitive |
| ≤4 | No reason to stop | Irrelevant to queries |

### Clarity (C)

| Score | Meaning |
| --- | --- |
| 9–10 | One idea; product + outcome obvious without reading body |
| 7–8 | Clear after short read |
| 5–6 | Multiple competing messages or weak product ID |
| ≤4 | Confusing |

### Product truth (P)

| Score | Meaning |
| --- | --- |
| 9–10 | Matches real SKU; no false cables/ports/UI |
| 7–8 | Recognizable; minor stylization |
| 5–6 | Wrong face, blank critical UI, or dubious props |
| ≤4 | Misrepresents product |

### Funnel fit (F)

| Score | Meaning |
| --- | --- |
| 9–10 | CTA + promise match stage and real offer state |
| 7–8 | Acceptable with minor CTA tweak |
| 5–6 | Mismatch (e.g. buy-now when unavailable) |
| ≤4 | Misleading |

### Platform fit (Pl)

| Score | Meaning |
| --- | --- |
| 9–10 | Correct ratio, safe zones, scannable type, channel-native |
| 7–8 | Usable; small crop/type nits |
| 5–6 | Wrong ratio or unreadable type |
| ≤4 | Unusable on placement |

---

## Appendix B — Related docs

- [GROK_BUILD_CREATIVE_WORKFLOW.md](GROK_BUILD_CREATIVE_WORKFLOW.md) — produce + review–regen loop  
- [PERFORMANCE_LEARNING.md](PERFORMANCE_LEARNING.md) — post-ship metrics  
- [EXPERIMENTS.md](EXPERIMENTS.md) — experiment evidence contract  
- `adclip formats` — channel size and copy length limits  
