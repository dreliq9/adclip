from datetime import date

from adclip.performance.experiment import (
    EvidenceThresholds,
    ExperimentArm,
    ExperimentRecord,
    evaluate_experiment,
    recommend_next_test,
)
from adclip.performance.schema import PerformanceMetrics, PerformanceObservation


def _experiment(metric="ctr", *, expected="higher", action_type=None, thresholds=None):
    return ExperimentRecord(
        id="exp_" + "a" * 32,
        campaign_id="cmp_test",
        name="Hook test",
        hypothesis="Treatment improves the primary rate",
        changed_factor="hook",
        control=ExperimentArm(
            role="control",
            creative_id="crv_control",
            variant_id="v01",
            format="meta_feed_4x5",
            factor_value="plain",
        ),
        treatment=ExperimentArm(
            role="treatment",
            creative_id="crv_treatment",
            variant_id="v02",
            format="meta_feed_4x5",
            factor_value="contrarian",
        ),
        primary_metric=metric,
        action_type=action_type,
        expected_direction=expected,
        thresholds=thresholds or EvidenceThresholds(
            min_denominator_per_arm=1000,
            min_events_per_arm=20,
        ),
    )


def _observation(creative_id, *, impressions, clicks, actions=None, values=None, spend=100):
    return PerformanceObservation(
        id="obs_" + creative_id,
        deployment_id="dep_" + creative_id,
        campaign_id="cmp_test",
        creative_id=creative_id,
        variant_id="v01" if creative_id.endswith("control") else "v02",
        platform="meta",
        account_id="act_1",
        external_ad_id="ad_1" if creative_id.endswith("control") else "ad_2",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 7),
        metrics=PerformanceMetrics(
            impressions=impressions,
            clicks=clicks,
            spend=spend,
            actions=actions or {},
            action_values=values or {},
        ),
    )


def test_ctr_hypothesis_supported_when_interval_excludes_zero():
    experiment = _experiment()
    observations = [
        _observation("crv_control", impressions=2000, clicks=100),
        _observation("crv_treatment", impressions=2000, clicks=180),
    ]
    result = evaluate_experiment(
        experiment,
        observations,
        since=date(2026, 8, 1),
        until=date(2026, 8, 7),
    )
    assert result["verdict"] == "supported"
    assert result["inferential"] is True
    assert result["causal_claim"] is False
    low, high = result["confidence"]["difference_interval"]
    assert low > 0
    assert high > low


def test_low_evidence_is_inconclusive():
    experiment = _experiment()
    observations = [
        _observation("crv_control", impressions=200, clicks=10),
        _observation("crv_treatment", impressions=200, clicks=20),
    ]
    result = evaluate_experiment(
        experiment,
        observations,
        since=date(2026, 8, 1),
        until=date(2026, 8, 7),
    )
    assert result["verdict"] == "inconclusive"
    assert result["reason"] == "minimum_evidence_not_met"
    recommendation = recommend_next_test(result)
    assert recommendation["action"] == "collect_more_evidence"


def test_roas_stays_descriptive_without_variance_evidence():
    experiment = _experiment(
        "roas",
        action_type="purchase",
        thresholds=EvidenceThresholds(
            min_denominator_per_arm=1,
            min_events_per_arm=5,
        ),
    )
    observations = [
        _observation(
            "crv_control",
            impressions=2000,
            clicks=100,
            actions={"purchase": 10},
            values={"purchase": 300},
            spend=100,
        ),
        _observation(
            "crv_treatment",
            impressions=2000,
            clicks=120,
            actions={"purchase": 15},
            values={"purchase": 600},
            spend=120,
        ),
    ]
    result = evaluate_experiment(
        experiment,
        observations,
        since=date(2026, 8, 1),
        until=date(2026, 8, 7),
    )
    assert result["treatment"]["value"] == 5.0
    assert result["inferential"] is False
    assert result["verdict"] == "inconclusive"
    assert "variance" in result["reason"]
