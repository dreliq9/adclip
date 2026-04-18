import json
from pathlib import Path

from adclip.mcp.campaign_tools import _campaign_status_impl


def test_missing_dir():
    out = _campaign_status_impl("/tmp/does-not-exist-adclip-test")
    assert out["ok"] is False
    assert "not found" in out["error"].lower()


def test_not_a_directory(tmp_path):
    f = tmp_path / "afile.txt"
    f.write_text("hi")
    out = _campaign_status_impl(str(f))
    assert out["ok"] is False
    assert "not a directory" in out["error"].lower()


def test_brief_only_midflight(tmp_path):
    (tmp_path / "brief.json").write_text(json.dumps({"product": "X"}))
    out = _campaign_status_impl(str(tmp_path))
    assert out["ok"] is True
    assert out["brief_found"] is True
    assert out["manifest_found"] is False
    assert out["brief"]["product"] == "X"
    assert out["rejected_count"] == 0


def test_full_manifest_and_variants(tmp_path):
    (tmp_path / "brief.json").write_text("{}")
    variants = tmp_path / "variants"
    (variants / "v01").mkdir(parents=True)
    (variants / "v01" / "meta_feed_4x5.png").write_bytes(b"x")
    (variants / "v02").mkdir(parents=True)
    (variants / "v02" / "google_rsa.json").write_text("{}")

    manifest = {
        "generated_at": "2026-04-18T00:00:00+00:00",
        "brief_summary": {"product": "X", "formats": ["meta_feed_4x5", "google_rsa"]},
        "total_cost_usd": 0.42,
        "entries": [
            {"variant_id": "v01", "format": "meta_feed_4x5", "path": "variants/v01/meta_feed_4x5.png"},
            {"variant_id": "v02", "format": "google_rsa", "path": "variants/v02/google_rsa.json"},
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    out = _campaign_status_impl(str(tmp_path))
    assert out["ok"] is True
    assert out["manifest_found"] is True
    assert out["variant_count"] == 2
    assert out["variant_formats"] == {"meta_feed_4x5": 1, "google_rsa": 1}
    assert out["total_cost_usd"] == 0.42
    assert out["missing_files"] == []
    assert out["variant_dirs_on_disk"] == ["v01", "v02"]


def test_missing_files_detected(tmp_path):
    manifest = {
        "entries": [
            {"variant_id": "v01", "format": "meta_feed_4x5", "path": "variants/v01/meta_feed_4x5.png"},
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    out = _campaign_status_impl(str(tmp_path))
    assert len(out["missing_files"]) == 1
    assert out["missing_files"][0]["variant_id"] == "v01"


def test_rejected_count(tmp_path):
    (tmp_path / "pool_rejected").mkdir()
    (tmp_path / "pool_rejected" / "rejected.json").write_text(
        json.dumps([{"x": 1}, {"x": 2}, {"x": 3}])
    )
    out = _campaign_status_impl(str(tmp_path))
    assert out["rejected_count"] == 3


def test_malformed_manifest_reported(tmp_path):
    (tmp_path / "manifest.json").write_text("{not valid json")
    out = _campaign_status_impl(str(tmp_path))
    assert out["ok"] is True
    assert out["manifest_found"] is False
    assert "manifest_error" in out
