from adclip.formats import FORMATS, get_format, AdFormatSpec


def test_meta_feed_4x5_spec():
    spec = get_format("meta_feed_4x5")
    assert spec.aspect == "4:5"
    assert spec.width == 1080
    assert spec.height == 1350
    assert spec.headline_max == 40
    assert spec.body_max == 125
    assert spec.kind == "static"


def test_stories_reels_unified_9x16():
    spec = get_format("stories_reels_9x16")
    assert spec.aspect == "9:16"
    assert spec.width == 1080
    assert spec.height == 1920
    assert spec.headline_max == 10  # overlay text on reels is short
    assert spec.kind == "video"


def test_google_rsa_text_only():
    spec = get_format("google_rsa")
    assert spec.kind == "text"
    assert spec.headline_max == 30
    assert spec.body_max == 90
    assert spec.rsa_max_headlines == 15
    assert spec.rsa_max_descriptions == 4


def test_unknown_format_raises():
    import pytest
    with pytest.raises(KeyError):
        get_format("not_a_format")


def test_all_formats_have_required_fields():
    for name, spec in FORMATS.items():
        assert spec.aspect, f"{name} missing aspect"
        assert spec.kind in ("static", "video", "text"), f"{name} bad kind"
        assert spec.headline_max > 0, f"{name} bad headline_max"
