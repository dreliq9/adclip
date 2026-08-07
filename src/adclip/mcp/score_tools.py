"""MCP tool: adclip_score_variants (re-rank existing variants)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from adclip.schema import AdBrief
from adclip.scoring import judge_pool, score_candidate


def _load_variant_copies(root: Path) -> list[dict]:
    """Load copy.json from every variants/*/ subdir."""
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
            copy = json.loads(copy_path.read_text())
        except json.JSONDecodeError:
            continue
        out.append({**copy, "variant_id": vdir.name})
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
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"brief.json invalid: {exc}"}

    copies = _load_variant_copies(root)
    if not copies:
        return {"ok": False, "error": "No variants with copy.json found"}

    if use_judge:
        if llm_provider is None:
            return {"ok": False, "error": "use_judge=True requires an llm_provider"}
        ranked = await judge_pool(copies, brief=brief, provider=llm_provider)
    else:
        scored = [{**copy, "heuristic_score": score_candidate(copy)} for copy in copies]
        scored.sort(key=lambda copy: copy["heuristic_score"], reverse=True)
        ranked = scored

    rank_summary = [
        {
            "variant_id": copy["variant_id"],
            "format": copy.get("format"),
            "heuristic_score": copy.get("heuristic_score"),
            "judge_score": copy.get("judge_score"),
        }
        for copy in ranked
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
                manifest = json.loads(manifest_path.read_text())
            except json.JSONDecodeError as exc:
                return {"ok": False, "error": f"manifest.json unreadable: {exc}"}
        else:
            manifest = {"entries": []}

        by_id = {row["variant_id"]: row for row in rank_summary}
        new_entries: list[dict] = []
        for row in rank_summary:
            variant_id = row["variant_id"]
            original = next(
                (
                    entry
                    for entry in manifest.get("entries", [])
                    if entry.get("variant_id") == variant_id
                ),
                None,
            )
            entry = (
                dict(original)
                if original
                else {"variant_id": variant_id, "format": row["format"]}
            )
            if row["heuristic_score"] is not None:
                entry["heuristic_score"] = row["heuristic_score"]
            else:
                entry.pop("heuristic_score", None)
            if row["judge_score"] is not None:
                entry["judge_score"] = row["judge_score"]
            else:
                entry.pop("judge_score", None)
            if row["judge_score"] is not None:
                entry["score"] = row["judge_score"]
            elif row["heuristic_score"] is not None:
                entry["score"] = row["heuristic_score"]
            else:
                entry.pop("score", None)
            new_entries.append(entry)

        for entry in manifest.get("entries", []):
            if entry.get("variant_id") not in by_id:
                new_entries.append(entry)

        manifest["entries"] = new_entries
        manifest_path.write_text(json.dumps(manifest, indent=2))
        result["manifest_updated"] = True

    return result


def register(mcp) -> None:
    @mcp.tool()
    async def adclip_score_variants(
        campaign_dir: str,
        use_judge: bool = False,
        llm_provider: str = "default",
        llm_model: str | None = None,
        write: bool = False,
    ) -> str:
        """Re-rank existing variants against brief.json.

        Heuristic mode is local and free. Judge mode accepts any registered
        text provider plus an independent provider-specific model ID.
        """
        provider = None
        selection = None
        if use_judge:
            from adclip.application import AdclipApplication

            app = AdclipApplication()
            try:
                provider, selection = app.resolve_text_provider_with_selection(
                    llm_provider,
                    model=llm_model,
                )
            except (RuntimeError, ValueError) as exc:
                return json.dumps({"ok": False, "error": str(exc)})

        result = await _score_variants_impl(
            campaign_dir,
            use_judge=use_judge,
            llm_provider=provider,
            write=write,
        )
        if result.get("ok") and selection is not None:
            result["models"] = {"text": selection.as_dict()}
        return json.dumps(result)
