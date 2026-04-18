import pytest
from pydantic import ValidationError

from adclip.schema import AdBrief


def minimal_brief(**overrides):
    defaults = dict(
        product="Taichi trading bot",
        value_prop="Paper-trade signals before risking cash",
        audience="Retail crypto traders",
        angles=["credibility", "curiosity"],
        tone="confident, dry",
        cta="Start paper trading",
        formats=["meta_feed_4x5"],
        output_dir="/tmp/adclip_test",
    )
    defaults.update(overrides)
    return AdBrief(**defaults)


def test_minimal_brief_parses():
    brief = minimal_brief()
    assert brief.variants == 5
    assert brief.pool_size == 15
    assert brief.variant_strategy == "angles"
    assert brief.policy_profile == "default"


def test_angles_must_be_non_empty():
    with pytest.raises(ValidationError):
        minimal_brief(angles=[])


def test_formats_must_be_known():
    with pytest.raises(ValidationError):
        minimal_brief(formats=["not_a_format"])


def test_pool_size_must_exceed_variants():
    with pytest.raises(ValidationError):
        minimal_brief(variants=10, pool_size=5)


def test_variant_strategy_allowed_values():
    for s in ["angles", "hooks", "visuals", "modular_components"]:
        brief = minimal_brief(variant_strategy=s)
        assert brief.variant_strategy == s
    with pytest.raises(ValidationError):
        minimal_brief(variant_strategy="bogus")


def test_policy_profile_allowed_values():
    for p in ["default", "crypto", "health", "alcohol", "financial_services"]:
        brief = minimal_brief(policy_profile=p)
        assert brief.policy_profile == p
    with pytest.raises(ValidationError):
        minimal_brief(policy_profile="bogus")


def test_budget_must_be_positive_if_set():
    with pytest.raises(ValidationError):
        minimal_brief(budget_usd=0)
    with pytest.raises(ValidationError):
        minimal_brief(budget_usd=-1)
    ok = minimal_brief(budget_usd=10.0)
    assert ok.budget_usd == 10.0
    assert minimal_brief(budget_usd=None).budget_usd is None


def test_variants_boundaries():
    with pytest.raises(ValidationError):
        minimal_brief(variants=0, pool_size=15)
    with pytest.raises(ValidationError):
        minimal_brief(variants=51, pool_size=60)
    assert minimal_brief(variants=1, pool_size=1).variants == 1
    assert minimal_brief(variants=50, pool_size=60).variants == 50


def test_pool_size_boundaries():
    with pytest.raises(ValidationError):
        minimal_brief(pool_size=0)
    with pytest.raises(ValidationError):
        minimal_brief(variants=1, pool_size=101)
    assert minimal_brief(variants=1, pool_size=1).pool_size == 1
    assert minimal_brief(variants=1, pool_size=100).pool_size == 100
