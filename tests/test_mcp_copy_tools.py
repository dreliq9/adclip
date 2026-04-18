import asyncio
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
    result = asyncio.run(_generate_copy_impl(json.dumps(BRIEF), provider_name="fake"))
    assert result["ok"] is True
    # variants=2 is the TOTAL output count (global rank, not per-bucket)
    assert len(result["winners"]) == 2
    assert "pool" in result
    assert len(result["pool"]) == 6  # 1 format × 2 angles × pool_size=3


def test_generate_copy_filters_policy_violations():
    brief = {**BRIEF, "must_include": ["NEVER_APPEARS_XYZ"]}
    result = asyncio.run(_generate_copy_impl(json.dumps(brief), provider_name="fake"))
    assert result["ok"] is True
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


def test_generate_copy_respects_use_judge_flag():
    """use_judge=True should parse without error. Judge is not exercised here
    because FakeLLMProvider doesn't branch on prompt shape, but the flag
    must survive the JSON -> AdBrief -> impl round trip."""
    brief = {**BRIEF, "use_judge": True}
    result = asyncio.run(_generate_copy_impl(json.dumps(brief), provider_name="fake"))
    assert result["ok"] is True


def test_get_provider_claude_cli_branch():
    """_get_provider should resolve 'claude-cli' without a session."""
    from adclip.mcp.copy_tools import _get_provider
    from adclip.claude_cli import ClaudeCliProvider

    provider = _get_provider("claude-cli", session=None)
    assert isinstance(provider, ClaudeCliProvider)


def test_get_provider_default_routes_to_claude_cli():
    """'default' should resolve to ClaudeCliProvider with no session —
    MCP sampling isn't supported by the Claude Code client, so the
    zero-config path must still work."""
    from adclip.mcp.copy_tools import _get_provider
    from adclip.claude_cli import ClaudeCliProvider

    provider = _get_provider("default", session=None)
    assert isinstance(provider, ClaudeCliProvider)


def test_get_provider_sampling_still_requires_session():
    """Explicit 'sampling' should fail fast without a session."""
    import pytest
    from adclip.mcp.copy_tools import _get_provider

    with pytest.raises(RuntimeError, match="sampling provider requires"):
        _get_provider("sampling", session=None)
