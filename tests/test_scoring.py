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
