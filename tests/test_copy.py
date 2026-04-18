from adclip.copy import generate_copy_pool, build_prompt
from adclip.llm import FakeLLMProvider
from adclip.schema import AdBrief


def _brief(**overrides):
    defaults = dict(
        product="Taichi", value_prop="Paper trade first",
        audience="Crypto traders",
        angles=["credibility"], tone="dry", cta="Start",
        formats=["meta_feed_4x5"],
        output_dir="/tmp/x", pool_size=3, variants=2,
    )
    defaults.update(overrides)
    return AdBrief(**defaults)


def test_build_prompt_mentions_format_constraints():
    brief = _brief()
    prompt = build_prompt(brief, format_name="meta_feed_4x5", angle="credibility")
    assert "meta_feed_4x5" in prompt or "4:5" in prompt.lower()
    assert "40" in prompt  # headline max
    assert "125" in prompt  # body max
    assert "credibility" in prompt
    assert brief.product in prompt


def test_generate_copy_pool_returns_candidates():
    brief = _brief(pool_size=4)
    provider = FakeLLMProvider()
    pool = generate_copy_pool(brief, provider=provider)
    # 1 format × 1 angle × pool_size = 4
    assert len(pool) == 4
    for c in pool:
        assert "headline" in c
        assert "body" in c
        assert "cta" in c
        assert c["format"] == "meta_feed_4x5"
        assert c["angle"] == "credibility"


def test_generate_copy_pool_multiple_angles_and_formats():
    brief = _brief(
        formats=["meta_feed_4x5", "google_rsa"],
        angles=["credibility", "curiosity"],
        pool_size=2,
    )
    provider = FakeLLMProvider()
    pool = generate_copy_pool(brief, provider=provider)
    # 2 formats × 2 angles × 2 per-call = 8
    assert len(pool) == 8
