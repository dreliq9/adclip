from datetime import date

import pytest

from adclip.performance.analysis import (
    compare_observations,
    select_window,
    summarize_observations,
)
from adclip.performance.schema import PerformanceMetrics, PerformanceObservation


def _observation(
    *,
    creative_id,
    variant_id,
    impressions,
    clicks,
    spend,
    purchases,
    value,
    action_report_time="conversion",
):
    return PerformanceObservation(
        id=f"obs_{creative_id}_{action_report_time}",
        deployment_id=f"dep_{creative_id}",
        campaign_id="cmp_1",
        creative_id=creative_id,
        variant_id=variant_id,
        platform="meta",
        account_id="act_1",
        external_ad_id=f"ad_{creative_id}",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 7),
        action_report_time=action_report_time,
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
    assert result["action_report_time"] == "conversion"
    assert result["rows"][0]["creative_id"] == "crv_a"
    assert result["rows"][0]["value"] == 3.0

    cpa = compare_observations(
        observations,
        metric="cost_per_action",
        action_type="purchase",
    )
    assert cpa["direction"] == "lower_is_better"
    assert cpa["rows"][0]["creative_id"] == "crv_a"


def test_same_dates_with_multiple_action_report_times_require_selection():
    observations = [
        _observation(
            creative_id="crv_a",
            variant_id="v01",
            impressions=1000,
            clicks=50,
            spend=50,
            purchases=5,
            value=100,
            action_report_time="conversion",
        ),
        _observation(
            creative_id="crv_a",
            variant_id="v01",
            impressions=1000,
            clicks=50,
            spend=50,
            purchases=8,
            value=150,
            action_report_time="impression",
        ),
    ]
    with pytest.raises(ValueError, match="Multiple action_report_time"):
        select_window(
            observations,
            since=date(2026, 8, 1),
            until=date(2026, 8, 7),
        )

    selected, window = select_window(
        observations,
        since=date(2026, 8, 1),
        until=date(2026, 8, 7),
        action_report_time="conversion",
    )
    assert window == (date(2026, 8, 1), date(2026, 8, 7), "conversion")
    assert len(selected) == 1
    assert selected[0].metrics.impressions == 1000


def test_auto_latest_prefers_conversion_action_report_time():
    observations = [
        _observation(
            creative_id="crv_a",
            variant_id="v01",
            impressions=1000,
            clicks=50,
            spend=50,
            purchases=5,
            value=100,
            action_report_time="conversion",
        ),
        _observation(
            creative_id="crv_a",
            variant_id="v01",
            impressions=1000,
            clicks=50,
            spend=50,
            purchases=8,
            value=150,
            action_report_time="impression",
        ),
    ]
    selected, window = select_window(observations)
    assert window == (date(2026, 8, 1), date(2026, 8, 7), "conversion")
    assert {item.action_report_time for item in selected} == {"conversion"}
