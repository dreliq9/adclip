import json
from pathlib import Path

from adclip.mcp.pipeline_tools import _fake_image_fn
from adclip.mcp.visual_tools import _generate_visuals_impl


def _brief_json(tmp_path: Path, formats: list[str] | None = None) -> str:
    return json.dumps(dict(
        product="X", value_prop="Y", audience="Z",
        angles=["credibility"], tone="dry", cta="Start",
        formats=formats or ["meta_feed_4x5"],
        output_dir=str(tmp_path / "camp"),
        variants=2, pool_size=2,
    ))


def _copy(**o):
    base = {
        "headline": "Headline", "body": "Body text over 30 characters for bonus.",
        "cta": "Start", "angle": "credibility", "format": "meta_feed_4x5",
    }
    base.update(o)
    return base


def test_missing_brief(tmp_path):
    out = _generate_visuals_impl("not-json", json.dumps([_copy()]), image_fn=_fake_image_fn)
    assert out["ok"] is False
    assert "brief_json" in out["error"]


def test_bad_copies_json(tmp_path):
    out = _generate_visuals_impl(_brief_json(tmp_path), "not-json", image_fn=_fake_image_fn)
    assert out["ok"] is False
    assert "copies_json" in out["error"]


def test_empty_copies_rejected(tmp_path):
    out = _generate_visuals_impl(_brief_json(tmp_path), "[]", image_fn=_fake_image_fn)
    assert out["ok"] is False
    assert "non-empty" in out["error"]


def test_missing_required_field(tmp_path):
    bad = _copy()
    del bad["headline"]
    out = _generate_visuals_impl(
        _brief_json(tmp_path), json.dumps([bad]), image_fn=_fake_image_fn,
    )
    assert out["ok"] is False
    assert "headline" in out["error"]


def test_happy_path_static_writes_files_and_manifest(tmp_path):
    out = _generate_visuals_impl(
        _brief_json(tmp_path),
        json.dumps([_copy(), _copy(headline="Second")]),
        image_fn=_fake_image_fn,
    )
    assert out["ok"] is True
    assert len(out["entries"]) == 2

    camp = tmp_path / "camp"
    assert (camp / "manifest.json").exists()
    assert (camp / "variants" / "v01" / "copy.json").exists()
    assert (camp / "variants" / "v01" / "meta_feed_4x5.png").exists()
    assert (camp / "variants" / "v02" / "meta_feed_4x5.png").exists()

    m = json.loads((camp / "manifest.json").read_text())
    assert m["entries"][0]["variant_id"] == "v01"
    assert m["entries"][0]["format"] == "meta_feed_4x5"


def test_text_format_writes_json_not_png(tmp_path):
    out = _generate_visuals_impl(
        _brief_json(tmp_path, formats=["google_rsa"]),
        json.dumps([_copy(format="google_rsa")]),
        image_fn=_fake_image_fn,
    )
    assert out["ok"] is True
    camp = tmp_path / "camp"
    assert (camp / "variants" / "v01" / "google_rsa.json").exists()
    assert not (camp / "variants" / "v01" / "google_rsa.png").exists()
    assert out["total_cost_usd"] == 0.0  # fake image, text format so never called


def test_unknown_format_returns_error(tmp_path):
    out = _generate_visuals_impl(
        _brief_json(tmp_path),
        json.dumps([_copy(format="not_a_real_format")]),
        image_fn=_fake_image_fn,
    )
    assert out["ok"] is False
    assert "not_a_real_format" in out["error"]


def test_video_format_passes_through_with_note(tmp_path):
    out = _generate_visuals_impl(
        _brief_json(tmp_path, formats=["tiktok_9x16"]),
        json.dumps([_copy(format="tiktok_9x16")]),
        image_fn=_fake_image_fn,
    )
    assert out["ok"] is True
    assert out["entries"][0]["path"] is None
    assert "video" in out["entries"][0]["note"].lower()
