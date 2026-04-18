import asyncio
import json

from adclip.judge import (
    build_judge_prompt,
    parse_judge_response,
    score_with_judge,
)
from adclip.llm import FakeLLMProvider
from adclip.schema import AdBrief


class ScriptedJudge(FakeLLMProvider):
    """Returns a scripted judge response regardless of prompt."""

    def __init__(self, scores: list[float]):
        self._scores = scores
        self._i = 0

    async def generate(self, prompt: str, n: int) -> str:
        s = self._scores[self._i % len(self._scores)]
        self._i += 1
        return json.dumps({
            "score": s,
            "rationale": "scripted",
            "flags": [],
        })


def _brief(**overrides):
    defaults = dict(
        product="Taichi", value_prop="Paper trade first",
        audience="Crypto traders",
        angles=["credibility"], tone="dry", cta="Start",
        formats=["meta_feed_4x5"],
        output_dir="/tmp/x",
    )
    defaults.update(overrides)
    return AdBrief(**defaults)


def test_build_judge_prompt_mentions_brief_fields():
    brief = _brief()
    cand = {"headline": "H", "body": "B", "cta": "C",
            "format": "meta_feed_4x5", "angle": "credibility"}
    prompt = build_judge_prompt(brief, cand)
    assert brief.product in prompt
    assert brief.value_prop in prompt
    assert "credibility" in prompt
    assert "H" in prompt
    assert "JSON" in prompt


def test_parse_judge_response_happy_path():
    raw = json.dumps({"score": 0.72, "rationale": "on-brief", "flags": []})
    out = parse_judge_response(raw)
    assert out["score"] == 0.72
    assert out["rationale"] == "on-brief"
    assert out["flags"] == []


def test_parse_judge_response_tolerates_prose_wrapper():
    raw = "Here's my evaluation:\n" + json.dumps({
        "score": 0.5, "rationale": "ok", "flags": ["weak_hook"]
    }) + "\nDone."
    out = parse_judge_response(raw)
    assert out["score"] == 0.5
    assert "weak_hook" in out["flags"]


def test_parse_judge_response_clamps_out_of_range():
    raw_high = json.dumps({"score": 2.0, "rationale": "x", "flags": []})
    raw_low = json.dumps({"score": -0.5, "rationale": "x", "flags": []})
    assert parse_judge_response(raw_high)["score"] == 1.0
    assert parse_judge_response(raw_low)["score"] == 0.0


def test_score_with_judge_attaches_judge_fields():
    brief = _brief()
    cand = {"headline": "H", "body": "B", "cta": "C",
            "format": "meta_feed_4x5", "angle": "credibility"}
    judge = ScriptedJudge(scores=[0.8])
    out = asyncio.run(score_with_judge(cand, brief, provider=judge))
    assert out["judge_score"] == 0.8
    assert out["judge_rationale"] == "scripted"
    assert out["judge_flags"] == []
    assert out["headline"] == "H"
