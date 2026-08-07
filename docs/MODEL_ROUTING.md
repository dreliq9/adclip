# Media Model Routing

**Status:** Active policy  
**Date:** 2026-08-07

## Purpose

A provider is infrastructure. A model is an implementation. A route is an
adclip policy for a marketing task.

```text
creative requirement -> route -> primary target + ordered fallbacks
```

Routes allow defaults to improve over time without changing campaign schemas or
embedding model names throughout the application. Explicit provider/model
selection always remains available.

## Current image routes

| Route | Primary | Ordered fallbacks | Notes |
| --- | --- | --- | --- |
| `general` | fal / GPT Image 2 medium | Nano Banana 2, FLUX.2 Pro | Default general marketing route |
| `premium` | direct OpenAI / GPT Image 2 high | fal GPT Image 2 high, FLUX.2 Max | Premium first-party render |
| `text-heavy` | fal / GPT Image 2 high | Nano Banana Pro, FLUX.2 Flex | Typography, packaging, diagrams, UI |
| `bulk` | fal / FLUX.2 Pro | Nano Banana 2 Lite, FLUX.2 | High-volume production |
| `draft` | fal / Nano Banana 2 Lite | FLUX.2 | Fast concept exploration |
| `brand-control` | fal / FLUX.2 Flex | GPT Image 2 high, FLUX.2 Pro | Palette and controlled layout |
| `reference` | Nano Banana 2 | GPT Image 2 edit | Cataloged; requires reference-image contract |
| `vector` | Recraft V4.1 Vector | — | Cataloged; requires Recraft/vector adapter |

## Current video routes

| Route | Primary | Ordered fallbacks | Notes |
| --- | --- | --- | --- |
| `general` | fal / Kling O3 Standard | Kling 3 Standard, Wan 2.6 | Default social/performance route |
| `premium` | fal / Veo 3.1 | Kling O3 with audio | Cinematic and native-audio output |
| `multi-shot` | fal / Seedance 2 Fast | Kling O3 intelligent shots | Directed sequences |
| `budget` | fal / Wan 2.6 | Kling O3 | Cost-controlled exploration |
| `multi-reference` | Seedance 2 Reference | — | Cataloged; requires reference-media contract |
| `image-animation` | Kling O3 image-to-video | — | Cataloged; requires start-image input |
| `edit` | Runway Aleph 2 | — | Cataloged; requires source-video and adapter |

Non-production routes are intentionally listed. Discovery and planning should
know they exist, while execution must reject them until the required inputs and
adapters are wired.

## Recommendation rules

The built-in recommender is deterministic and inspectable:

- text-heavy image -> `text-heavy`
- reference images -> `reference`
- vector output -> `vector`
- exact brand control -> `brand-control`
- premium image/video -> `premium`
- high-volume image -> `bulk`
- draft image -> `draft`
- existing footage -> `edit`
- reference media -> `multi-reference`
- directed multi-shot -> `multi-shot`
- high-volume/draft video -> `budget`
- otherwise -> `general`

It is not an LLM judgment and does not infer requirements that were not supplied.

## Overrides

Selection precedence:

1. explicit route;
2. `ADCLIP_IMAGE_ROUTE` / `ADCLIP_VIDEO_ROUTE`;
3. `general`.

Within a route:

1. explicit provider;
2. modality provider environment variable;
3. route primary provider.

Then:

1. explicit model;
2. modality model environment variable;
3. matching route target model;
4. route primary model.

Explicit provider/model values are recorded with the selected route in
provenance.

## Fallbacks

Fallbacks are recommendations, not automatic retries. Automatically spending on
another model after a failed call would make billing and reproducibility
ambiguous. A future authorized retry policy must define:

```text
maximum additional cost
maximum attempts
eligible failure classes
approved fallback targets
whether partial results may be retained
```

Until then, the caller chooses the next target explicitly.

## Bake-off governance

Defaults should be revisited regularly with the fixed media bake-off suite.
Run plans without spending:

```bash
adclip bakeoff --modality image --routes general,text-heavy,bulk
adclip bakeoff --modality video --routes general,premium,multi-shot,budget
```

Execution requires `--execute` and normal paid-provider authorization. The
suite records latency, cost, artifact hashes, failure status, and evaluation
dimensions. Human scores should be added without removing raw artifacts or
provider metadata.

Promote a new default only when it wins on the task-specific dimensions at an
acceptable cost and failure rate. Keep prior results so route changes are
traceable over time.

## Adding a route

A new route should include:

- a stable task-oriented name;
- one primary target;
- zero or more ordered fallbacks;
- generation options that are valid for the selected model family;
- explicit required inputs/adapters;
- `production_ready=False` until end-to-end execution is tested;
- bake-off fixtures or evidence that distinguish the task from existing routes.

Do not add routes merely to mirror every model in a provider catalog. Routes
represent durable marketing tasks, while model catalogs change frequently.
