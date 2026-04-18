from adclip.scoring import score_candidate, rank_pool


def test_longer_body_within_limit_scores_higher_than_very_short():
    # Deterministic heuristics — no LLM involved at this stage.
    short = {"headline": "Hi", "body": "Buy.", "cta": "Go", "format": "meta_feed_4x5", "angle": "a"}
    rich = {
        "headline": "Paper-trade our bot before risking real cash",
        "body": "Skeptical? Run our signals on paper for a week. No card required.",
        "cta": "Start paper trading",
        "format": "meta_feed_4x5", "angle": "a",
    }
    assert score_candidate(rich) > score_candidate(short)


def test_rank_pool_keeps_top_n():
    pool = [
        {"headline": "Bad " * 2, "body": "x", "cta": "c", "format": "meta_feed_4x5", "angle": "a"},
        {"headline": "Better headline here", "body": "Longer body text that reads well.", "cta": "Start", "format": "meta_feed_4x5", "angle": "a"},
        {"headline": "Another good one maybe", "body": "Decent body, reasonably informative.", "cta": "Try", "format": "meta_feed_4x5", "angle": "a"},
    ]
    top = rank_pool(pool, n=2)
    assert len(top) == 2
    # The "short" one should be dropped
    assert all(c["headline"] != "Bad Bad " for c in top)


def test_rank_pool_per_format_angle_quota():
    pool = []
    for i in range(5):
        pool.append({
            "headline": f"H{i} more text to score",
            "body": f"Body {i} is reasonably fleshed out.",
            "cta": "Go",
            "format": "meta_feed_4x5",
            "angle": "credibility",
        })
    for i in range(5):
        pool.append({
            "headline": f"H{i} curiosity variant text",
            "body": f"Curiosity body {i} with length.",
            "cta": "Go",
            "format": "meta_feed_4x5",
            "angle": "curiosity",
        })
    # 2 variants per (format, angle) should yield 4 total
    top = rank_pool(pool, n=2, per_bucket=True)
    assert len(top) == 4
    angles = {c["angle"] for c in top}
    assert angles == {"credibility", "curiosity"}


import asyncio

from adclip.scoring import rank_with_judge
from adclip.schema import AdBrief


class _ScriptedJudgeProvider:
    """Returns scores in round-robin order from the list."""

    def __init__(self, scores):
        self._scores = scores
        self._i = 0

    async def generate(self, prompt: str, n: int):
        import json
        s = self._scores[self._i % len(self._scores)]
        self._i += 1
        return json.dumps({"score": s, "rationale": "", "flags": []})


def _brief_min():
    return AdBrief(
        product="X", value_prop="Y", audience="Z",
        angles=["a"], tone="t", cta="c",
        formats=["meta_feed_4x5"],
        output_dir="/tmp/x",
    )


def test_rank_with_judge_orders_by_judge_score():
    pool = [
        {"headline": f"H{i}", "body": f"B{i}", "cta": "C",
         "format": "meta_feed_4x5", "angle": "a"}
        for i in range(3)
    ]
    provider = _ScriptedJudgeProvider(scores=[0.2, 0.9, 0.5])
    brief = _brief_min()
    top = asyncio.run(rank_with_judge(pool, brief=brief, provider=provider, n=2))
    assert len(top) == 2
    assert top[0]["headline"] == "H1"  # 0.9
    assert top[1]["headline"] == "H2"  # 0.5
    assert all("judge_score" in c for c in top)


def test_rank_with_judge_per_bucket():
    pool = []
    for angle in ["credibility", "curiosity"]:
        for i in range(3):
            pool.append({
                "headline": f"H-{angle}-{i}",
                "body": "B", "cta": "C",
                "format": "meta_feed_4x5", "angle": angle,
            })
    provider = _ScriptedJudgeProvider(
        scores=[0.1, 0.9, 0.5, 0.4, 0.2, 0.8]
    )
    brief = _brief_min()
    top = asyncio.run(rank_with_judge(
        pool, brief=brief, provider=provider, n=1, per_bucket=True,
    ))
    assert len(top) == 2
    angles = {c["angle"] for c in top}
    assert angles == {"credibility", "curiosity"}
