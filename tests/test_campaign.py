import json
from pathlib import Path

from adclip.campaign import init_campaign_dir, write_manifest
from adclip.schema import AdBrief


def _brief(tmp_path, **overrides):
    defaults = dict(
        product="X", value_prop="Y", audience="Z",
        angles=["a"], tone="t", cta="c",
        formats=["meta_feed_4x5"],
        output_dir=str(tmp_path / "campaign"),
    )
    defaults.update(overrides)
    return AdBrief(**defaults)


def test_init_creates_tree(tmp_path):
    brief = _brief(tmp_path)
    init_campaign_dir(brief)
    root = Path(brief.output_dir)
    assert (root / "brief.json").exists()
    assert (root / "variants").is_dir()
    assert (root / "pool_rejected").is_dir()


def test_brief_json_roundtrip(tmp_path):
    brief = _brief(tmp_path, product="ProductZ")
    init_campaign_dir(brief)
    loaded = json.loads((Path(brief.output_dir) / "brief.json").read_text())
    assert loaded["product"] == "ProductZ"


def test_write_manifest(tmp_path):
    brief = _brief(tmp_path)
    init_campaign_dir(brief)
    write_manifest(brief, entries=[
        {"variant_id": "v01", "format": "meta_feed_4x5", "path": "variants/v01/meta_feed_4x5.png", "score": 0.6},
    ], cost_usd=0.12)
    m = json.loads((Path(brief.output_dir) / "manifest.json").read_text())
    assert m["total_cost_usd"] == 0.12
    assert len(m["entries"]) == 1
