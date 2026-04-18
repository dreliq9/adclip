"""MCP tool: adclip_campaign_status (read-only campaign state)."""

from __future__ import annotations

import json
from pathlib import Path


def _campaign_status_impl(campaign_dir: str) -> dict:
    root = Path(campaign_dir)
    if not root.exists():
        return {"ok": False, "error": f"Campaign dir not found: {campaign_dir}"}
    if not root.is_dir():
        return {"ok": False, "error": f"Not a directory: {campaign_dir}"}

    status: dict = {
        "ok": True,
        "campaign_dir": str(root.resolve()),
        "brief_found": False,
        "manifest_found": False,
        "rejected_count": 0,
    }

    brief_path = root / "brief.json"
    if brief_path.exists():
        status["brief_found"] = True
        try:
            status["brief"] = json.loads(brief_path.read_text())
        except json.JSONDecodeError as e:
            status["brief_error"] = f"brief.json unreadable: {e}"

    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        try:
            m = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as e:
            status["manifest_error"] = f"manifest.json unreadable: {e}"
        else:
            status["manifest_found"] = True
            status["generated_at"] = m.get("generated_at")
            status["brief_summary"] = m.get("brief_summary")
            status["total_cost_usd"] = m.get("total_cost_usd", 0.0)

            entries = m.get("entries", [])
            status["variant_count"] = len(entries)
            status["entries"] = entries

            fmt_counts: dict[str, int] = {}
            for e in entries:
                key = e.get("format", "unknown")
                fmt_counts[key] = fmt_counts.get(key, 0) + 1
            status["variant_formats"] = fmt_counts

            missing: list[dict] = []
            for e in entries:
                p = e.get("path")
                if p and not (root / p).exists():
                    missing.append({
                        "variant_id": e.get("variant_id"),
                        "expected_path": p,
                    })
            status["missing_files"] = missing

    rejected_path = root / "pool_rejected" / "rejected.json"
    if rejected_path.exists():
        try:
            rejected = json.loads(rejected_path.read_text())
        except json.JSONDecodeError as e:
            status["rejected_error"] = f"rejected.json unreadable: {e}"
        else:
            if isinstance(rejected, list):
                status["rejected_count"] = len(rejected)
            else:
                status["rejected_error"] = (
                    f"rejected.json has unexpected shape "
                    f"({type(rejected).__name__}); expected list"
                )

    variants_dir = root / "variants"
    if variants_dir.exists():
        status["variant_dirs_on_disk"] = sorted(
            d.name for d in variants_dir.iterdir() if d.is_dir()
        )

    return status


def register(mcp) -> None:
    @mcp.tool()
    def adclip_campaign_status(campaign_dir: str) -> str:
        """Report on a campaign directory: manifest, variants, costs, missing files.

        Read-only. Works on a completed campaign or a mid-flight one
        (brief.json but no manifest yet).

        Args:
            campaign_dir: path to the campaign output directory.
        """
        return json.dumps(_campaign_status_impl(campaign_dir))
