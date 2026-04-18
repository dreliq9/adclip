import asyncio
import json

from adclip.heal import build_heal_prompt, heal_candidate
from adclip.schema import AdBrief


class _ScriptedHealProvider:
    def __init__(self, replies: list[dict]):
        self._replies = replies
        self._i = 0

    async def generate(self, prompt: str, n: int):
        r = self._replies[self._i % len(self._replies)]
        self._i += 1
        return json.dumps({"candidates": [r]})


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


def test_build_heal_prompt_embeds_original_and_violations():
    brief = _brief()
    cand = {
        "headline": "Guaranteed Returns",
        "body": "Guaranteed profits every month",
        "cta": "Sign up",
        "format": "meta_feed_4x5", "angle": "a",
    }
    violations = ["copy contains blocked phrase: 'guaranteed return'"]
    prompt = build_heal_prompt(brief, cand, violations)
    assert "Guaranteed Returns" in prompt
    assert "guaranteed return" in prompt
    assert "crypto" in prompt
    assert "do not change the core message" in prompt.lower() or "preserve" in prompt.lower()


def test_heal_candidate_rewrites_once(monkeypatch):
    brief = _brief()
    cand = {
        "headline": "Guaranteed 10x returns",
        "body": "Guaranteed profit every month",
        "cta": "Sign up",
        "format": "meta_feed_4x5", "angle": "a",
    }
    violations = ["copy contains blocked phrase: 'guaranteed return'"]
    provider = _ScriptedHealProvider(replies=[
        {"headline": "Try paper trading first",
         "body": "Run our signals risk-observed for a week. No card required.",
         "cta": "Start paper trading"},
    ])
    healed = asyncio.run(heal_candidate(
        cand, brief=brief, violations=violations,
        provider=provider, max_retries=1,
    ))
    assert healed is not None
    joined = (healed["headline"] + healed["body"] + healed["cta"]).lower()
    assert "guaranteed" not in joined
    assert healed["format"] == "meta_feed_4x5"
    assert healed["angle"] == "a"
    assert healed["healed_from"]["headline"] == "Guaranteed 10x returns"
    assert healed["heal_attempts"] == 1


def test_heal_candidate_gives_up_after_max_retries():
    brief = _brief()
    cand = {
        "headline": "Guaranteed returns",
        "body": "Guaranteed profit",
        "cta": "Sign up",
        "format": "meta_feed_4x5", "angle": "a",
    }
    violations = ["copy contains blocked phrase: 'guaranteed return'"]
    provider = _ScriptedHealProvider(replies=[
        {"headline": "Guaranteed profit ahead", "body": "Guaranteed profit every day", "cta": "Go"},
        {"headline": "Still guaranteed profit", "body": "Guaranteed return incoming", "cta": "Go"},
    ])
    healed = asyncio.run(heal_candidate(
        cand, brief=brief, violations=violations,
        provider=provider, max_retries=2,
    ))
    assert healed is None
