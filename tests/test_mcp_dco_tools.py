import json
from pathlib import Path

from PIL import Image

from adclip.mcp.dco_tools import _export_dco_impl


def _write_variant(
    campaign: Path, vid: str, *,
    copy: dict, rendered: bool = True,
) -> Path:
    vdir = campaign / "variants" / vid
    vdir.mkdir(parents=True)
    (vdir / "copy.json").write_text(json.dumps(copy))
    fmt = copy["format"]
    if rendered and fmt != "google_rsa":
        Image.new("RGB", (100, 100), color=(200, 0, 0)).save(vdir / f"{fmt}.png")
    return vdir


def test_missing_campaign():
    out = _export_dco_impl("/tmp/does-not-exist-adclip")
    assert out["ok"] is False


def test_no_variants(tmp_path):
    (tmp_path / "variants").mkdir()
    out = _export_dco_impl(str(tmp_path))
    assert out["ok"] is False
    assert "No variants" in out["error"]


def test_exports_components_and_dedups(tmp_path):
    _write_variant(tmp_path, "v01", copy={
        "headline": "Hook A", "body": "Body text one.", "cta": "Go",
        "angle": "credibility", "format": "meta_feed_4x5",
    })
    _write_variant(tmp_path, "v02", copy={
        "headline": "Hook A",  # duplicate
        "body": "Body text two.",
        "cta": "Go",  # duplicate
        "angle": "curiosity", "format": "meta_feed_1x1",
    })
    _write_variant(tmp_path, "v03", copy={
        "headline": "Hook B", "body": "Body text three.", "cta": "Start now",
        "angle": "credibility", "format": "meta_feed_1x1",
    })

    out = _export_dco_impl(str(tmp_path))
    assert out["ok"] is True
    assert out["headline_count"] == 2
    assert out["body_count"] == 3
    assert out["cta_count"] == 2
    assert out["image_count"] == 3

    dco = tmp_path / "dco_components"
    assert json.loads((dco / "headlines.json").read_text()) == ["Hook A", "Hook B"]
    assert json.loads((dco / "ctas.json").read_text()) == ["Go", "Start now"]
    assert (dco / "images" / "img_v01_4x5.png").exists()
    assert (dco / "images" / "img_v02_1x1.png").exists()
    assert (dco / "images" / "img_v03_1x1.png").exists()

    idx = json.loads((dco / "images.json").read_text())
    assert len(idx) == 3
    assert {e["aspect"] for e in idx} == {"4:5", "1:1"}


def test_text_only_variant_contributes_copy_not_image(tmp_path):
    _write_variant(tmp_path, "v01", copy={
        "headline": "TextHook", "body": "Short body.",
        "cta": "Learn more",
        "angle": "credibility", "format": "google_rsa",
    }, rendered=False)
    out = _export_dco_impl(str(tmp_path))
    assert out["ok"] is True
    assert out["headline_count"] == 1
    assert out["image_count"] == 0
    assert not (tmp_path / "dco_components" / "images" / "img_v01_text.png").exists()


def test_variant_without_rendered_png_is_skipped_for_images(tmp_path):
    _write_variant(tmp_path, "v01", copy={
        "headline": "H", "body": "B", "cta": "C",
        "angle": "credibility", "format": "meta_feed_4x5",
    }, rendered=False)
    out = _export_dco_impl(str(tmp_path))
    assert out["ok"] is True
    assert out["headline_count"] == 1
    assert out["image_count"] == 0


def test_unreadable_copy_is_skipped(tmp_path):
    _write_variant(tmp_path, "v01", copy={
        "headline": "Good", "body": "B", "cta": "C",
        "angle": "a", "format": "meta_feed_4x5",
    })
    bad = tmp_path / "variants" / "v02"
    bad.mkdir()
    (bad / "copy.json").write_text("{broken")

    out = _export_dco_impl(str(tmp_path))
    assert out["ok"] is True
    assert out["headline_count"] == 1


def test_empty_strings_filtered_out(tmp_path):
    _write_variant(tmp_path, "v01", copy={
        "headline": "", "body": "", "cta": "",
        "angle": "a", "format": "meta_feed_4x5",
    })
    _write_variant(tmp_path, "v02", copy={
        "headline": "Real", "body": "Real body", "cta": "Go",
        "angle": "a", "format": "meta_feed_4x5",
    })
    out = _export_dco_impl(str(tmp_path))
    assert out["headline_count"] == 1
    assert out["body_count"] == 1
    assert out["cta_count"] == 1
