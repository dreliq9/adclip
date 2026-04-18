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


from adclip.scoring import ensure_format_coverage


def test_ensure_format_coverage_swaps_lowest_winner_for_missing_format():
    winners = [
        {"headline": "A", "format": "fmtA", "angle": "a", "judge_score": 0.9},
        {"headline": "B", "format": "fmtA", "angle": "a", "judge_score": 0.6},
    ]
    survivors = winners + [
        {"headline": "C", "format": "fmtB", "angle": "a", "judge_score": 0.7},
        {"headline": "D", "format": "fmtB", "angle": "a", "judge_score": 0.4},
    ]
    out = ensure_format_coverage(winners, survivors, ["fmtA", "fmtB"])
    fmts = {w["format"] for w in out}
    assert fmts == {"fmtA", "fmtB"}
    # The fmtA 0.9 must be retained; 0.6 replaced by best fmtB (0.7).
    headlines = sorted(w["headline"] for w in out)
    assert headlines == ["A", "C"]


def test_ensure_format_coverage_noop_when_already_covered():
    winners = [
        {"headline": "A", "format": "fmtA", "angle": "a", "judge_score": 0.9},
        {"headline": "C", "format": "fmtB", "angle": "a", "judge_score": 0.5},
    ]
    survivors = winners + [
        {"headline": "D", "format": "fmtB", "angle": "a", "judge_score": 0.8},
    ]
    out = ensure_format_coverage(winners, survivors, ["fmtA", "fmtB"])
    assert out == winners  # leave well enough alone


def test_ensure_format_coverage_skips_when_no_survivors_of_missing_format():
    winners = [
        {"headline": "A", "format": "fmtA", "angle": "a", "judge_score": 0.9},
        {"headline": "B", "format": "fmtA", "angle": "a", "judge_score": 0.6},
    ]
    out = ensure_format_coverage(winners, winners, ["fmtA", "fmtB"])
    assert out == winners  # fmtB absent from survivors → can't swap


from adclip.scoring import ensure_variant_diversity, jaccard_similarity


def test_jaccard_similarity_identical():
    a = {"headline": "skeptical good", "body": "paper trade"}
    b = {"headline": "skeptical good", "body": "paper trade"}
    assert jaccard_similarity(a, b) == 1.0


def test_jaccard_similarity_disjoint():
    a = {"headline": "alpha beta", "body": "gamma delta"}
    b = {"headline": "epsilon zeta", "body": "eta theta"}
    assert jaccard_similarity(a, b) == 0.0


def test_jaccard_similarity_partial_overlap():
    a = {"headline": "paper trade first", "body": "before you fund"}
    b = {"headline": "paper trade first", "body": "see the track record"}
    s = jaccard_similarity(a, b)
    assert 0.0 < s < 1.0


def test_ensure_variant_diversity_swaps_near_duplicate():
    winners = [
        {"headline": "Skeptical paper trade", "body": "Try first.",
         "format": "fmt", "angle": "a", "judge_score": 0.9},
        {"headline": "Skeptical paper trade", "body": "Try first.",
         "format": "fmt", "angle": "a", "judge_score": 0.8},
    ]
    alt = {"headline": "What if you tested", "body": "Wildly different words entirely.",
           "format": "fmt", "angle": "b", "judge_score": 0.7}
    pool = winners + [alt]
    out = ensure_variant_diversity(winners, pool, threshold=0.5)
    headlines = [w["headline"] for w in out]
    assert "What if you tested" in headlines
    assert any(w.get("judge_score") == 0.9 for w in out)
    # Lower-scored dup should have been replaced.
    assert sum(1 for w in out if w["headline"] == "Skeptical paper trade") == 1


def test_ensure_variant_diversity_noop_when_unique():
    winners = [
        {"headline": "Alpha hook entirely", "body": "Words one here.",
         "format": "fmt", "angle": "a", "judge_score": 0.9},
        {"headline": "Beta something else", "body": "Totally different body.",
         "format": "fmt", "angle": "b", "judge_score": 0.8},
    ]
    out = ensure_variant_diversity(winners, winners, threshold=0.6)
    assert out == winners


def test_rank_pool_attaches_heuristic_score():
    pool = [
        {"headline": "Better headline here", "body": "Longer body text that reads well.",
         "cta": "Start", "format": "meta_feed_4x5", "angle": "a"},
        {"headline": "Another good one maybe", "body": "Decent body, reasonably informative.",
         "cta": "Try", "format": "meta_feed_4x5", "angle": "a"},
    ]
    top = rank_pool(pool, n=2)
    assert all("heuristic_score" in c for c in top)
    assert all(0.0 <= c["heuristic_score"] <= 1.0 for c in top)


def test_judge_pool_attaches_heuristic_score():
    pool = [
        {"headline": "H0 headline", "body": "B0 body words here.", "cta": "C",
         "format": "meta_feed_4x5", "angle": "a"},
        {"headline": "H1 headline", "body": "B1 body words here.", "cta": "C",
         "format": "meta_feed_4x5", "angle": "a"},
    ]
    from adclip.scoring import judge_pool
    provider = _ScriptedJudgeProvider(scores=[0.7, 0.3])
    brief = _brief_min()
    out = asyncio.run(judge_pool(pool, brief=brief, provider=provider))
    assert all("heuristic_score" in c for c in out)
    assert all("judge_score" in c for c in out)


def test_judge_pool_runs_calls_concurrently():
    """Gather dispatches all score calls at once rather than awaiting each serially."""
    import asyncio as _asyncio

    class _ConcurrencyTracker:
        def __init__(self, scores):
            self._scores = scores
            self._i = 0
            self._peak = 0
            self._live = 0

        async def generate(self, prompt, n):
            self._live += 1
            self._peak = max(self._peak, self._live)
            await _asyncio.sleep(0)  # yield to loop
            await _asyncio.sleep(0)
            s = self._scores[self._i % len(self._scores)]
            self._i += 1
            import json
            out = json.dumps({"score": s, "rationale": "", "flags": []})
            self._live -= 1
            return out

    from adclip.scoring import judge_pool
    pool = [
        {"headline": f"H{i}", "body": f"B{i}", "cta": "C",
         "format": "meta_feed_4x5", "angle": "a"}
        for i in range(5)
    ]
    tracker = _ConcurrencyTracker(scores=[0.5] * 5)
    brief = _brief_min()
    asyncio.run(judge_pool(pool, brief=brief, provider=tracker))
    assert tracker._peak >= 2, f"expected concurrent dispatch, peak={tracker._peak}"


def test_ensure_variant_diversity_preserves_format_coverage():
    # Dup pair spans two formats; swap candidates only exist in fmtA,
    # so swapping would break fmtB coverage → no-op.
    winners = [
        {"headline": "paper trade first", "body": "skeptical body text",
         "format": "fmtA", "angle": "a", "judge_score": 0.9},
        {"headline": "paper trade first", "body": "skeptical body text",
         "format": "fmtB", "angle": "a", "judge_score": 0.8},
    ]
    alt = {"headline": "Totally different hook", "body": "And different body.",
           "format": "fmtA", "angle": "b", "judge_score": 0.7}
    pool = winners + [alt]
    out = ensure_variant_diversity(winners, pool, threshold=0.5)
    fmts = {w["format"] for w in out}
    assert fmts == {"fmtA", "fmtB"}
