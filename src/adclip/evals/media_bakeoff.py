"""Repeatable task-level bake-offs for image and video routes.

The harness is dry-run by default. Executing a plan requires the caller to opt
in explicitly and still passes through adclip's runtime and paid-API policy.
Results are JSON artifacts suitable for later human or automated scoring.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Literal

from adclip.model_routing import get_media_route
from adclip.providers.media import resolve_image_provider, resolve_video_provider
from adclip.runtime import RuntimePolicy


Modality = Literal["image", "video"]


@dataclass(frozen=True)
class BakeoffFixture:
    name: str
    modality: Modality
    prompt: str
    format_name: str
    evaluation_dimensions: tuple[str, ...]


@dataclass(frozen=True)
class BakeoffJob:
    fixture: BakeoffFixture
    route: str
    repetition: int


IMAGE_FIXTURES: tuple[BakeoffFixture, ...] = (
    BakeoffFixture(
        name="general-hero",
        modality="image",
        prompt=(
            "Premium advertising hero image for a compact modular solar power "
            "station on a clean workbench at golden hour. Accurate materials, "
            "credible electronics, strong negative space, no visible text."
        ),
        format_name="meta_feed_4x5",
        evaluation_dimensions=("prompt_adherence", "realism", "composition"),
    ),
    BakeoffFixture(
        name="text-heavy-promotion",
        modality="image",
        prompt=(
            "Design a polished social promotion with the exact readable headline "
            "BUILD. TEST. LEARN. and the subhead Faster creative experiments, "
            "fewer guesses. Use a clean modern grid and no additional words."
        ),
        format_name="meta_feed_4x5",
        evaluation_dimensions=("ocr_accuracy", "layout", "prompt_adherence"),
    ),
    BakeoffFixture(
        name="brand-color-control",
        modality="image",
        prompt=(
            "Minimal product campaign composition using only #0B1F33, #13B8A6, "
            "white, and neutral gray. Crisp geometry, restrained premium style, "
            "no text and no color cast."
        ),
        format_name="google_display_square",
        evaluation_dimensions=("color_accuracy", "composition", "brand_fit"),
    ),
    BakeoffFixture(
        name="package-fidelity",
        modality="image",
        prompt=(
            "Photorealistic studio product image of a rectangular portable power "
            "station with two AC outlets, four USB-C ports, one circular display, "
            "matte charcoal housing, and no invented controls or labels."
        ),
        format_name="meta_feed_1x1",
        evaluation_dimensions=("object_count", "structural_fidelity", "realism"),
    ),
)


VIDEO_FIXTURES: tuple[BakeoffFixture, ...] = (
    BakeoffFixture(
        name="product-motion",
        modality="video",
        prompt=(
            "A compact power station sits on a workshop bench. Slow controlled "
            "camera orbit, realistic reflections, subtle indicator lights, no "
            "shape changes, no extra ports, premium commercial lighting."
        ),
        format_name="tiktok_9x16",
        evaluation_dimensions=("motion_coherence", "product_stability", "realism"),
    ),
    BakeoffFixture(
        name="dialogue-social-ad",
        modality="video",
        prompt=(
            "A practical engineer looks to camera in a bright workshop and says "
            '"Test the idea before you scale the spend." Natural voice, accurate '
            "lip sync, subtle ambient workshop audio, one continuous shot."
        ),
        format_name="youtube_shorts_9x16",
        evaluation_dimensions=("lip_sync", "audio_quality", "subject_consistency"),
    ),
    BakeoffFixture(
        name="multi-shot-story",
        modality="video",
        prompt=(
            "Three-shot commercial: close-up of a rough sketch, cut to a prototype "
            "being tested, cut to a finished product in use outdoors. Maintain the "
            "same product identity and coherent color grade across all shots."
        ),
        format_name="stories_reels_9x16",
        evaluation_dimensions=("shot_structure", "continuity", "prompt_adherence"),
    ),
)


DEFAULT_ROUTES: dict[Modality, tuple[str, ...]] = {
    "image": ("general", "text-heavy", "bulk", "draft", "brand-control", "premium"),
    "video": ("general", "premium", "multi-shot", "budget"),
}


def fixtures_for(modality: Modality) -> tuple[BakeoffFixture, ...]:
    return IMAGE_FIXTURES if modality == "image" else VIDEO_FIXTURES


def build_bakeoff_plan(
    modality: Modality,
    *,
    routes: Iterable[str] | None = None,
    repetitions: int = 1,
) -> list[BakeoffJob]:
    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")
    selected_routes = tuple(routes or DEFAULT_ROUTES[modality])
    for route_name in selected_routes:
        route = get_media_route(modality, route_name)
        if not route.production_ready:
            raise ValueError(
                f"Route {route_name!r} requires {', '.join(route.requires)} and "
                "cannot run in this bake-off yet"
            )
    return [
        BakeoffJob(fixture=fixture, route=route_name, repetition=repetition)
        for fixture in fixtures_for(modality)
        for route_name in selected_routes
        for repetition in range(1, repetitions + 1)
    ]


def serialize_plan(jobs: Iterable[BakeoffJob]) -> list[dict[str, object]]:
    output = []
    for job in jobs:
        route = get_media_route(job.fixture.modality, job.route)
        output.append({
            "fixture": asdict(job.fixture),
            "route": route.as_dict(),
            "repetition": job.repetition,
        })
    return output


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_bakeoff(
    jobs: list[BakeoffJob],
    *,
    output_dir: str | Path,
    execute: bool = False,
    runtime_policy: RuntimePolicy | None = None,
) -> dict[str, object]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    plan_payload = serialize_plan(jobs)
    (root / "plan.json").write_text(json.dumps(plan_payload, indent=2))
    if not execute:
        return {
            "ok": True,
            "executed": False,
            "job_count": len(jobs),
            "plan_path": str(root / "plan.json"),
        }

    policy = runtime_policy or RuntimePolicy.from_env()
    results: list[dict[str, object]] = []
    for job in jobs:
        route = get_media_route(job.fixture.modality, job.route)
        job_dir = root / job.fixture.name / job.route / f"r{job.repetition:02d}"
        job_dir.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        row: dict[str, object] = {
            "fixture": job.fixture.name,
            "route": job.route,
            "repetition": job.repetition,
            "evaluation_dimensions": list(job.fixture.evaluation_dimensions),
            "human_score": None,
            "notes": "",
        }
        try:
            if job.fixture.modality == "image":
                binding = resolve_image_provider(route=job.route, policy=policy)
            else:
                binding = resolve_video_provider(route=job.route, policy=policy)
            row["selection"] = binding.provenance()
            result = binding(
                job.fixture.prompt,
                format_name=job.fixture.format_name,
                output_dir=str(job_dir),
                seed=job.repetition,
            )
            artifact = Path(result.local_path)
            row.update({
                "status": "ok",
                "artifact_path": str(artifact),
                "artifact_sha256": _sha256(artifact),
                "cost_usd": float(result.cost_usd),
            })
        except Exception as exc:
            row.update({"status": "error", "error": str(exc), "cost_usd": 0.0})
        row["latency_seconds"] = round(time.perf_counter() - started, 3)
        results.append(row)

    results_path = root / "results.json"
    results_path.write_text(json.dumps(results, indent=2))
    return {
        "ok": all(row["status"] == "ok" for row in results),
        "executed": True,
        "job_count": len(jobs),
        "results_path": str(results_path),
        "total_cost_usd": round(sum(float(row["cost_usd"]) for row in results), 4),
        "results": results,
    }
