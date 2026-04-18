"""Top-level pipeline: brief -> copy pool -> policy filter -> rank ->
image gen -> compose -> render -> manifest.

v0.1 supports static formats end-to-end. Video formats are accepted in
the brief but skipped with a manifest note (until Phase 6 video path lands).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from adclip.campaign import init_campaign_dir, variant_dir, write_manifest
from adclip.compose import build_overlay_plan
from adclip.copy import generate_copy_pool
from adclip.formats import get_format
from adclip.image_gen import build_image_prompt, generate_image
from adclip.llm import LLMProvider, default_provider
from adclip.policy import check_copy
from adclip.render import render_static_ad
from adclip.schema import AdBrief
from adclip.scoring import rank_pool


def _filter(pool: list[dict], brief: AdBrief) -> tuple[list[dict], list[dict]]:
    survivors: list[dict] = []
    rejected: list[dict] = []
    for c in pool:
        fmt = get_format(c["format"])
        r = check_copy(
            headline=c["headline"], body=c["body"], cta=c["cta"],
            format_spec=fmt, profile=brief.policy_profile,
            must_include=brief.must_include, must_avoid=brief.must_avoid,
        )
        if r.violations:
            rejected.append({**c, "violations": r.violations, "warnings": r.warnings})
        else:
            survivors.append({**c, "warnings": r.warnings})
    return survivors, rejected


def _default_image_fn(prompt, *, format_name, output_dir, seed):
    return generate_image(
        prompt, format_name=format_name, output_dir=output_dir, seed=seed
    )


async def run_pipeline(
    brief: AdBrief,
    *,
    llm_provider: LLMProvider | None = None,
    image_fn: Callable | None = None,
) -> dict:
    llm_provider = llm_provider or default_provider()
    image_fn = image_fn or _default_image_fn

    root = init_campaign_dir(brief)

    # Copy
    pool = await generate_copy_pool(brief, provider=llm_provider)
    survivors, rejected = _filter(pool, brief)
    winners = rank_pool(survivors, n=brief.variants, per_bucket=True)

    # Dump rejected
    if rejected:
        (root / "pool_rejected" / "rejected.json").write_text(
            json.dumps(rejected, indent=2)
        )

    entries: list[dict] = []
    total_cost = 0.0

    for i, w in enumerate(winners, start=1):
        vid = f"v{i:02d}"
        vdir = variant_dir(brief, vid)
        (vdir / "copy.json").write_text(json.dumps(w, indent=2))

        fmt = get_format(w["format"])
        if fmt.kind == "text":
            # Text-only ad -- the copy IS the deliverable
            (vdir / f"{w['format']}.json").write_text(json.dumps(w, indent=2))
            entries.append({
                "variant_id": vid,
                "format": w["format"],
                "path": f"variants/{vid}/{w['format']}.json",
                "score": None,
            })
            continue

        if fmt.kind == "static":
            prompt = build_image_prompt(brief, format_name=w["format"], variant_copy=w)
            img = image_fn(
                prompt, format_name=w["format"], output_dir=str(vdir), seed=i,
            )
            total_cost += img.cost_usd
            plan = build_overlay_plan(
                format_name=w["format"], copy=w, logo_path=brief.logo_path,
            )
            final = vdir / f"{w['format']}.png"
            render_static_ad(plan, background=img.local_path, output=str(final))
            entries.append({
                "variant_id": vid,
                "format": w["format"],
                "path": f"variants/{vid}/{w['format']}.png",
                "score": None,
            })
            continue

        # video: to be implemented in Phase 6 follow-up
        entries.append({
            "variant_id": vid,
            "format": w["format"],
            "path": None,
            "score": None,
            "note": "video formats not yet implemented in pipeline",
        })

    write_manifest(brief, entries=entries, cost_usd=total_cost)
    return {
        "ok": True,
        "entries": entries,
        "rejected_count": len(rejected),
        "total_cost_usd": total_cost,
    }
