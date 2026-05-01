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
from adclip.render import render_static_ad, render_video_ad
from adclip.schema import AdBrief
from adclip.video_gen import generate_ad_clip
from adclip.scoring import (
    ensure_format_coverage,
    ensure_variant_diversity,
    rank_pool,
)
from adclip.semantic_policy import semantic_check


async def _filter_with_heal(
    pool: list[dict],
    brief: AdBrief,
    *,
    llm_provider,
) -> tuple[list[dict], list[dict]]:
    """Split pool into (survivors, permanently_rejected).

    Violators with brief.heal_violations > 0 are sent to heal.heal_candidate.
    Successful heals land in survivors; failed heals go to rejected.
    When brief.use_semantic_policy is set, each compliance check combines
    the literal blocklist with an LLM semantic pass.
    """
    from adclip.heal import heal_candidate

    async def compliance_check(c: dict):
        fmt = get_format(c["format"])
        r = check_copy(
            headline=c["headline"], body=c["body"], cta=c["cta"],
            format_spec=fmt, profile=brief.policy_profile,
            must_include=brief.must_include, must_avoid=brief.must_avoid,
        )
        if brief.use_semantic_policy:
            sem = await semantic_check(c, brief=brief, provider=llm_provider)
            r.violations.extend(sem)
        return r

    survivors: list[dict] = []
    rejected: list[dict] = []

    for c in pool:
        r = await compliance_check(c)
        if not r.violations:
            survivors.append({**c, "warnings": r.warnings})
            continue

        if brief.heal_violations > 0:
            healed = await heal_candidate(
                c, brief=brief, violations=r.violations,
                provider=llm_provider, max_retries=brief.heal_violations,
                check_fn=compliance_check,
            )
            if healed is not None:
                survivors.append(healed)
                continue

        rejected.append({
            **c, "violations": r.violations, "warnings": r.warnings,
        })

    return survivors, rejected


def _default_image_fn(prompt, *, format_name, output_dir, seed):
    return generate_image(
        prompt, format_name=format_name, output_dir=output_dir, seed=seed
    )


def _default_video_fn(prompt, *, format_name, output_dir, seed):
    return generate_ad_clip(
        prompt, format_name=format_name, output_dir=output_dir, seed=seed,
    )


def _entry_from_winner(winner: dict, *, variant_id: str, path: str | None) -> dict:
    entry: dict = {
        "variant_id": variant_id,
        "format": winner["format"],
        "path": path,
        "score": winner.get("judge_score"),
    }
    for key in ("judge_score", "judge_rationale", "judge_flags",
                "heuristic_score", "heal_attempts", "healed_from"):
        if key in winner:
            entry[key] = winner[key]
    return entry


async def run_pipeline(
    brief: AdBrief,
    *,
    llm_provider: LLMProvider | None = None,
    image_fn: Callable | None = None,
    video_fn: Callable | None = None,
) -> dict:
    llm_provider = llm_provider or default_provider()
    image_fn = image_fn or _default_image_fn
    video_fn = video_fn or _default_video_fn

    root = init_campaign_dir(brief)

    # Copy
    pool = await generate_copy_pool(brief, provider=llm_provider)
    survivors, rejected = await _filter_with_heal(
        pool, brief, llm_provider=llm_provider,
    )

    # `variants` is total output count (not per bucket). Users who want
    # per-angle or per-format coverage should size `variants` accordingly.
    if brief.use_judge:
        from adclip.scoring import judge_pool
        judged = await judge_pool(survivors, brief=brief, provider=llm_provider)
        winners = judged[: brief.variants]
        coverage_pool = judged
    else:
        winners = rank_pool(survivors, n=brief.variants)
        coverage_pool = survivors

    if len(brief.formats) > 1:
        winners = ensure_format_coverage(winners, coverage_pool, brief.formats)

    if len(winners) > 1:
        winners = ensure_variant_diversity(winners, coverage_pool)

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
            entries.append(_entry_from_winner(
                w, variant_id=vid,
                path=f"variants/{vid}/{w['format']}.json",
            ))
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
            entries.append(_entry_from_winner(
                w, variant_id=vid,
                path=f"variants/{vid}/{w['format']}.png",
            ))
            continue

        # video
        prompt = build_image_prompt(brief, format_name=w["format"], variant_copy=w)
        clip = video_fn(
            prompt, format_name=w["format"], output_dir=str(vdir), seed=i,
        )
        total_cost += clip.cost_usd
        plan = build_overlay_plan(
            format_name=w["format"], copy=w, logo_path=brief.logo_path,
        )
        final = vdir / f"{w['format']}.mp4"
        render_video_ad(plan, background=clip.local_path, output=str(final))
        entries.append(_entry_from_winner(
            w, variant_id=vid,
            path=f"variants/{vid}/{w['format']}.mp4",
        ))

    write_manifest(brief, entries=entries, cost_usd=total_cost)
    return {
        "ok": True,
        "entries": entries,
        "rejected_count": len(rejected),
        "total_cost_usd": total_cost,
    }
