import json

from adclip.mcp.brief_tools import (
    _brief_validate_impl,
    _list_formats_impl,
    _estimate_cost_impl,
)


def test_brief_validate_happy_path():
    payload = dict(
        product="X", value_prop="Y", audience="Z",
        angles=["a"], tone="t", cta="c",
        formats=["meta_feed_4x5"],
        output_dir="/tmp/x",
    )
    result = _brief_validate_impl(json.dumps(payload))
    assert result["ok"] is True
    assert "brief" in result


def test_brief_validate_bad_format():
    payload = dict(
        product="X", value_prop="Y", audience="Z",
        angles=["a"], tone="t", cta="c",
        formats=["nope"],
        output_dir="/tmp/x",
    )
    result = _brief_validate_impl(json.dumps(payload))
    assert result["ok"] is False
    assert "Unknown formats" in result["error"]


def test_list_formats():
    out = _list_formats_impl()
    assert len(out["formats"]) >= 10
    names = [f["name"] for f in out["formats"]]
    assert "meta_feed_4x5" in names
    assert "stories_reels_9x16" in names
    assert "google_rsa" in names


def test_estimate_cost_returns_breakdown():
    payload = dict(
        product="X", value_prop="Y", audience="Z",
        angles=["a"], tone="t", cta="c",
        formats=["google_rsa"],
        output_dir="/tmp/x",
    )
    out = _estimate_cost_impl(json.dumps(payload))
    assert out["ok"] is True
    assert out["total_usd"] >= 0
    assert "breakdown" in out
