import json

from adclip.mcp.copy_tools import (
    _generate_copy_impl,
    _policy_check_impl,
)


BRIEF = dict(
    product="Taichi", value_prop="Paper-trade first",
    audience="Crypto traders",
    angles=["credibility", "curiosity"],
    tone="dry", cta="Start",
    formats=["meta_feed_4x5"],
    output_dir="/tmp/x", pool_size=3, variants=2,
    policy_profile="crypto",
)


def test_generate_copy_with_fake_provider():
    result = _generate_copy_impl(json.dumps(BRIEF), provider_name="fake")
    assert result["ok"] is True
    # 1 format × 2 angles, rank per bucket, variants=2 → 4 winners
    assert len(result["winners"]) == 4
    assert "pool" in result
    assert len(result["pool"]) == 6  # 1 format × 2 angles × pool_size=3


def test_generate_copy_filters_policy_violations():
    # Fake provider returns "Headline 1", "Body text 1 for the test.", etc.
    # Add must_include that the fake never produces.
    brief = {**BRIEF, "must_include": ["NEVER_APPEARS_XYZ"]}
    result = _generate_copy_impl(json.dumps(brief), provider_name="fake")
    assert result["ok"] is True
    # All candidates violate must_include → winners empty
    assert len(result["winners"]) == 0
    assert len(result["rejected"]) > 0


def test_policy_check_standalone():
    result = _policy_check_impl(
        headline="Guaranteed 10x returns",
        body="Guaranteed profit every month",
        cta="Buy now",
        format_name="meta_feed_4x5",
        profile="crypto",
        must_include_json="[]",
        must_avoid_json="[]",
    )
    assert result["ok"] is True
    assert len(result["violations"]) >= 1
