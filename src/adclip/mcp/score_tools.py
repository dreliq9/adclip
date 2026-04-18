"""MCP tool: adclip_score_variants (re-rank existing variants)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from adclip.schema import AdBrief
from adclip.scoring import judge_pool, score_candidate


def _load_variant_copies(root: Path) -> list[dict]:
    """Load copy.json from every variants/*/ subdir. Returns dicts with
    ``variant_id`` and format attached.
    """
    variants_dir = root / "variants"
    if not variants_dir.exists():
        return []
    out: list[dict] = []
    for vdir in sorted(variants_dir.iterdir()):
        if not vdir.is_dir():
            continue
        copy_path = vdir / "copy.json"
        if not copy_path.exists():
            continue
        try:
            c = json.loads(copy_path.read_text())
        except json.JSONDecodeError:
            continue
        out.append({**c, "variant_id": vdir.name})
    return out


async def _score_variants_impl(
    campaign_dir: str,
    *,
    use_judge: bool = False,
    llm_provider=None,
    write: bool = False,
) -> dict:
    root = Path(campaign_dir)
    if not root.is_dir():
        return {"ok": False, "error": f"Campaign dir not found: {campaign_dir}"}

    brief_path = root / "brief.json"
    if not brief_path.exists():
        return {"ok": False, "error": f"brief.json missing in {campaign_dir}"}

    try:
        brief = AdBrief(**json.loads(brief_path.read_text()))
    except (ValidationError, ValueError, json.JSONDecodeError) as e:
        return {"ok": False, "error": f"brief.json invalid: {e}"}

    copies = _load_variant_copies(root)
    if not copies:
        return {"ok": False, "error": "No variants with copy.json found"}

    if use_judge:
        if llm_provider is None:
            return {"ok": False, "error": "use_judge=True requires an llm_provider"}
        ranked = await judge_pool(copies, brief=brief, provider=llm_provider)
    else:
        scored = [{**c, "heuristic_score": score_candidate(c)} for c in copies]
        scored.sort(key=lambda c: c["heuristic_score"], reverse=True)
        ranked = scored

    rank_summary = [
        {
            "variant_id": c["variant_id"],
            "format": c.get("format"),
            "heuristic_score": c.get("heuristic_score"),
            "judge_score": c.get("judge_score"),
        }
        for c in ranked
    ]

    result: dict = {
        "ok": True,
        "use_judge": use_judge,
        "ranked": rank_summary,
    }

    if write:
        manifest_path = root / "manifest.json"
        if manifest_path.exists():
            try:
                m = json.loads(manifest_path.read_text())
            except json.JSONDecodeError as e:
                return {"ok": False, "error": f"manifest.json unreadable: {e}"}
        else:
            m = {"entries": []}

        by_id = {r["variant_id"]: r for r in rank_summary}
        new_entries: list[dict] = []
        for r in rank_summary:
            vid = r["variant_id"]
            original = next(
                (e for e in m.get("entries", []) if e.get("variant_id") == vid),
                None,
            )
            entry = dict(original) if original else {"variant_id": vid, "format": r["format"]}
            # Overwrite score fields with the current ranking's values (or clear
            # them) so write-through never leaves stale scores from prior runs.
            if r["heuristic_score"] is not None:
                entry["heuristic_score"] = r["heuristic_score"]
            else:
                entry.pop("heuristic_score", None)
            if r["judge_score"] is not None:
                entry["judge_score"] = r["judge_score"]
            else:
                entry.pop("judge_score", None)
            if r["judge_score"] is not None:
                entry["score"] = r["judge_score"]
            elif r["heuristic_score"] is not None:
                entry["score"] = r["heuristic_score"]
            else:
                entry.pop("score", None)
            new_entries.append(entry)

        # Carry over entries that exist on disk but weren't in the rank (e.g. missing copy.json)
        for e in m.get("entries", []):
            if e.get("variant_id") not in by_id:
                new_entries.append(e)

        m["entries"] = new_entries
        manifest_path.write_text(json.dumps(m, indent=2))
        result["manifest_updated"] = True

    return result


def register(mcp) -> None:
    @mcp.tool()
    async def adclip_score_variants(
        campaign_dir: str,
        use_judge: bool = False,
        llm_provider: str = "default",
        write: bool = False,
    ) -> str:
        """Re-rank existing variants against brief.json.

        Heuristic by default (no LLM call, free). Pass ``use_judge=True``
        to use the LLM judge — requires a provider.

        Args:
            campaign_dir: path to the campaign output directory.
            use_judge: if True, use the LLM judge instead of the heuristic.
            llm_provider: provider name for the judge path
                ('default'/'claude-cli', 'sampling', 'anthropic', 'fake').
                Ignored when use_judge=False.
            write: if True, update manifest.json entry order and score fields.
        """
        llm = None
        if use_judge:
            from adclip.mcp.pipeline_tools import _resolve_llm
            try:
                llm = _resolve_llm(llm_provider, session=None)
            except RuntimeError as e:
                return json.dumps({"ok": False, "error": str(e)})

        result = await _score_variants_impl(
            campaign_dir,
            use_judge=use_judge,
            llm_provider=llm,
            write=write,
        )
        return json.dumps(result)
