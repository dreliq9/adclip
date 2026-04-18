import json
from pathlib import Path

from PIL import Image

from adclip.mcp.render_tools import _render_variant_impl


def _seed_campaign(tmp_path: Path, *, logo: bool = False) -> Path:
    (tmp_path / "variants").mkdir()
    brief = {"product": "X", "logo_path": None}
    if logo:
        lp = tmp_path / "logo.png"
        Image.new("RGBA", (100, 100), color=(255, 0, 255, 255)).save(lp)
        brief["logo_path"] = str(lp)
    (tmp_path / "brief.json").write_text(json.dumps(brief))
    return tmp_path


def _make_variant(campaign: Path, vid: str, *, copy: dict, bg_format: str | None = None) -> Path:
    vdir = campaign / "variants" / vid
    vdir.mkdir(parents=True)
    (vdir / "copy.json").write_text(json.dumps(copy))
    if bg_format:
        Image.new("RGB", (1080, 1350), color=(40, 40, 80)).save(
            vdir / f"{bg_format}_1.png"
        )
    return vdir


def test_missing_campaign():
    out = _render_variant_impl("/tmp/does-not-exist-adclip", "v01")
    assert out["ok"] is False
    assert "not found" in out["error"].lower()


def test_missing_variant(tmp_path):
    _seed_campaign(tmp_path)
    out = _render_variant_impl(str(tmp_path), "v99")
    assert out["ok"] is False
    assert "Variant not found" in out["error"]


def test_missing_copy_json(tmp_path):
    _seed_campaign(tmp_path)
    (tmp_path / "variants" / "v01").mkdir()
    out = _render_variant_impl(str(tmp_path), "v01")
    assert out["ok"] is False
    assert "copy.json missing" in out["error"]


def test_text_format_writes_json(tmp_path):
    _seed_campaign(tmp_path)
    copy = {"headline": "H", "body": "B", "cta": "C", "angle": "a", "format": "google_rsa"}
    _make_variant(tmp_path, "v01", copy=copy)

    out = _render_variant_impl(str(tmp_path), "v01")
    assert out["ok"] is True
    assert out["kind"] == "text"
    assert out["format"] == "google_rsa"
    rendered = tmp_path / "variants" / "v01" / "google_rsa.json"
    assert rendered.exists()
    assert json.loads(rendered.read_text())["headline"] == "H"


def test_static_format_composites_with_existing_background(tmp_path):
    _seed_campaign(tmp_path)
    copy = {"headline": "Hello", "body": "B", "cta": "Go", "angle": "a", "format": "meta_feed_4x5"}
    _make_variant(tmp_path, "v01", copy=copy, bg_format="meta_feed_4x5")

    out = _render_variant_impl(str(tmp_path), "v01")
    assert out["ok"] is True
    assert out["kind"] == "static"
    rendered = tmp_path / "variants" / "v01" / "meta_feed_4x5.png"
    assert rendered.exists()
    assert rendered.stat().st_size > 5_000


def test_static_missing_background_returns_error(tmp_path):
    _seed_campaign(tmp_path)
    copy = {"headline": "H", "body": "B", "cta": "C", "angle": "a", "format": "meta_feed_4x5"}
    _make_variant(tmp_path, "v01", copy=copy)  # no bg

    out = _render_variant_impl(str(tmp_path), "v01")
    assert out["ok"] is False
    assert "background" in out["error"].lower()


def test_static_with_user_supplied_background(tmp_path):
    _seed_campaign(tmp_path)
    copy = {"headline": "H", "body": "B", "cta": "C", "angle": "a", "format": "meta_feed_4x5"}
    _make_variant(tmp_path, "v01", copy=copy)

    user_bg = tmp_path / "custom.png"
    Image.new("RGB", (1080, 1350), color=(200, 0, 0)).save(user_bg)

    out = _render_variant_impl(
        str(tmp_path), "v01", background=str(user_bg),
    )
    assert out["ok"] is True
    assert (tmp_path / "variants" / "v01" / "meta_feed_4x5.png").exists()


def test_video_format_rejected(tmp_path):
    _seed_campaign(tmp_path)
    copy = {"headline": "H", "body": "B", "cta": "C", "angle": "a", "format": "tiktok_9x16"}
    _make_variant(tmp_path, "v01", copy=copy)

    out = _render_variant_impl(str(tmp_path), "v01")
    assert out["ok"] is False
    assert "video" in out["error"].lower()


def test_logo_from_brief_is_applied(tmp_path):
    _seed_campaign(tmp_path, logo=True)
    copy = {"headline": "H", "body": "B", "cta": "C", "angle": "a", "format": "meta_feed_4x5"}
    _make_variant(tmp_path, "v01", copy=copy, bg_format="meta_feed_4x5")

    out = _render_variant_impl(str(tmp_path), "v01")
    assert out["ok"] is True

    rendered = Image.open(tmp_path / "variants" / "v01" / "meta_feed_4x5.png").convert("RGB")
    # Logo is bottom-right, max_width=1080//8=135, fixed in compose. Probe
    # a pixel clearly inside that square.
    w, h = rendered.size
    r, g, b = rendered.getpixel((w - 32 - 50, h - 32 - 50))
    assert (r, g, b) == (255, 0, 255)


def test_override_format_name(tmp_path):
    _seed_campaign(tmp_path)
    copy = {"headline": "H", "body": "B", "cta": "C", "angle": "a", "format": "meta_feed_4x5"}
    vdir = _make_variant(tmp_path, "v01", copy=copy)
    # Supply a 1:1 bg under the override format name
    Image.new("RGB", (1080, 1080), color=(40, 40, 80)).save(vdir / "meta_feed_1x1_1.png")

    out = _render_variant_impl(str(tmp_path), "v01", format_name="meta_feed_1x1")
    assert out["ok"] is True
    assert out["format"] == "meta_feed_1x1"
    assert (vdir / "meta_feed_1x1.png").exists()
