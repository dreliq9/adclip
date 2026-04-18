from adclip.cost import estimate_cost, CostEstimate
from adclip.schema import AdBrief


def _brief(**overrides):
    defaults = dict(
        product="X", value_prop="Y", audience="Z",
        angles=["a"], tone="neutral", cta="buy",
        formats=["meta_feed_4x5"],
        output_dir="/tmp/x",
    )
    defaults.update(overrides)
    return AdBrief(**defaults)


def test_text_only_brief_has_zero_image_and_video_cost():
    brief = _brief(formats=["google_rsa"], variants=5, pool_size=15)
    est = estimate_cost(brief)
    assert est.image_cost_usd == 0.0
    assert est.video_cost_usd == 0.0
    assert est.llm_cost_usd > 0
    assert est.total_usd == est.llm_cost_usd


def test_static_format_adds_image_cost():
    brief = _brief(formats=["meta_feed_4x5"], variants=5, pool_size=5)
    est = estimate_cost(brief)
    assert est.image_cost_usd > 0
    assert est.video_cost_usd == 0.0


def test_video_format_adds_video_cost():
    brief = _brief(formats=["stories_reels_9x16"], variants=3, pool_size=3)
    est = estimate_cost(brief)
    assert est.video_cost_usd > 0


def test_budget_check_over_budget():
    brief = _brief(
        formats=["stories_reels_9x16"],
        variants=10, pool_size=20,
        budget_usd=0.01,
    )
    est = estimate_cost(brief)
    assert est.over_budget is True


def test_budget_check_under_budget():
    brief = _brief(
        formats=["google_rsa"],
        variants=3, pool_size=5,
        budget_usd=100.0,
    )
    est = estimate_cost(brief)
    assert est.over_budget is False
