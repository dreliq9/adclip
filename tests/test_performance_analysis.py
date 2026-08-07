from datetime import date

from adclip.performance.analysis import compare_observations, summarize_observations
from adclip.performance.schema import PerformanceMetrics, PerformanceObservation


def _observation(*, creative_id, variant_id, impressions, clicks, spend, purchases, value):
    return PerformanceObservation(
        id=f"obs_{creative_id}",
        deployment_id=f"dep_{creative_id}",
        campaign_id="cmp_1",
        creative_id=creative_id,
        variant_id=variant_id,
        platform="meta",
        account_id="act_1",
        external_ad_id=f"ad_{creative_id}",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 7),
        metrics=PerformanceMetrics(
            impressions=impressions,
            clicks=clicks,
            spend=spend,
            actions={"purchase": purchases},
            action_values={"purchase": value},
        ),
    )


def test_action_rate_uses_clicks_and_preserves_impression_rate():
    summary = summarize_observations([
        _observation(
            creative_id="crv_a",
            variant_id="v01",
            impressions=1000,
            clicks=100,
            spend=50,
            purchases=10,
            value=200,
        )
    ])[0]
    assert summary["derived"]["action_rates_per_click"]["purchase"] == 0.1
    assert summary["derived"]["action_rates_per_impression"]["purchase"] == 0.01


def test_comparison_does_not_claim_causality_and_ranks_directionally():
    observations = [
        _observation(
            creative_id="crv_a",
            variant_id="v01",
            impressions=1000,
            clicks=100,
            spend=100,
            purchases=10,
            value=300,
        ),
        _observation(
            creative_id="crv_b",
            variant_id="v02",
            impressions=1000,
            clicks=80,
            spend=80,
            purchases=4,
            value=100,
        ),
    ]
    result = compare_observations(
        observations,
        metric="roas",
        action_type="purchase",
    )
    assert result["causal_claim"] is False
    assert result["descriptive_only"] is True
    assert result["rows"][0]["creative_id"] == "crv_a"
    assert result["rows"][0]["value"] == 3.0

    cpa = compare_observations(
        observations,
        metric="cost_per_action",
        action_type="purchase",
    )
    assert cpa["direction"] == "lower_is_better"
    assert cpa["rows"][0]["creative_id"] == "crv_a"
