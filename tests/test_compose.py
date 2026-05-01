from adclip.compose import build_overlay_plan


def test_static_overlay_plan_has_headline_and_cta():
    plan = build_overlay_plan(
        format_name="meta_feed_4x5",
        copy={"headline": "H", "body": "B", "cta": "C", "angle": "a"},
        logo_path=None,
    )
    assert plan["format"] == "meta_feed_4x5"
    assert plan["kind"] == "static"
    texts = [o for o in plan["overlays"] if o["type"] == "text"]
    headlines = [o for o in texts if o["role"] == "headline"]
    ctas = [o for o in texts if o["role"] == "cta"]
    assert len(headlines) == 1
    assert len(ctas) == 1


def test_logo_overlay_emitted_when_provided():
    plan = build_overlay_plan(
        format_name="meta_feed_4x5",
        copy={"headline": "H", "body": "B", "cta": "C", "angle": "a"},
        logo_path="/path/to/logo.png",
    )
    images = [o for o in plan["overlays"] if o["type"] == "image"]
    assert len(images) == 1
    assert images[0]["path"] == "/path/to/logo.png"


def test_text_only_format_uses_kind_text():
    plan = build_overlay_plan(
        format_name="google_rsa",
        copy={"headline": "H", "body": "B", "cta": "C", "angle": "a"},
        logo_path=None,
    )
    assert plan["kind"] == "text"
    assert plan["overlays"] == []


def test_video_plan_carries_dimensions_and_lufs_target():
    plan = build_overlay_plan(
        format_name="tiktok_9x16",
        copy={"headline": "H", "body": "B", "cta": "C", "angle": "a"},
        logo_path=None,
    )
    assert plan["kind"] == "video"
    assert plan["width"] == 1080
    assert plan["height"] == 1920
    assert plan["lufs_target"] == -14.0
    roles = [o["role"] for o in plan["overlays"] if o["type"] == "text"]
    assert "headline" in roles and "cta" in roles
