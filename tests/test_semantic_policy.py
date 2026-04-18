import asyncio

from adclip.schema import AdBrief
from adclip.semantic_policy import (
    build_semantic_prompt,
    parse_semantic_response,
    semantic_check,
)


def _brief(**overrides):
    defaults = dict(
        product="X", value_prop="Y", audience="Z",
        angles=["a"], tone="t", cta="c",
        formats=["meta_feed_4x5"],
        output_dir="/tmp/x",
        policy_profile="crypto",
    )
    defaults.update(overrides)
    return AdBrief(**defaults)


class _ScriptedProvider:
    def __init__(self, payload: str):
        self._payload = payload
        self.calls = 0

    async def generate(self, prompt, n):
        self.calls += 1
        return self._payload


def test_parse_semantic_response_extracts_violations():
    raw = '{"violations": ["implies no-risk", "overclaim on returns"]}'
    assert parse_semantic_response(raw) == ["implies no-risk", "overclaim on returns"]


def test_parse_semantic_response_tolerates_prose_wrapping():
    raw = 'Sure, here is the JSON:\n{"violations": ["hype"]}\nall done.'
    assert parse_semantic_response(raw) == ["hype"]


def test_parse_semantic_response_empty_list_means_clean():
    assert parse_semantic_response('{"violations": []}') == []


def test_build_semantic_prompt_embeds_profile_intent_and_copy():
    brief = _brief()
    cand = {
        "headline": "Risk Zero Trading",
        "body": "Pay nothing.",
        "cta": "Go",
        "format": "meta_feed_4x5",
        "angle": "credibility",
    }
    prompt = build_semantic_prompt(brief, cand)
    assert "Risk Zero Trading" in prompt
    assert "Pay nothing" in prompt
    lower = prompt.lower()
    assert "guarantee" in lower or "risk" in lower
    assert "crypto" in lower


def test_semantic_check_prefixes_violations_with_semantic_marker():
    cand = {
        "headline": "Risk Zero", "body": "Zero risk, real gains.", "cta": "Go",
        "format": "meta_feed_4x5", "angle": "a",
    }
    provider = _ScriptedProvider('{"violations": ["implies risk elimination"]}')
    out = asyncio.run(semantic_check(cand, brief=_brief(), provider=provider))
    assert out == ["semantic: implies risk elimination"]
    assert provider.calls == 1


def test_semantic_check_returns_empty_on_clean_copy():
    cand = {
        "headline": "Test before you commit", "body": "Paper trade first.", "cta": "Go",
        "format": "meta_feed_4x5", "angle": "a",
    }
    provider = _ScriptedProvider('{"violations": []}')
    out = asyncio.run(semantic_check(cand, brief=_brief(), provider=provider))
    assert out == []
