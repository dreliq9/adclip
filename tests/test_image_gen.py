import pytest

from adclip.image_gen import (
    build_image_prompt,
    MODELS,
    estimate_image_cost,
)
from adclip.schema import AdBrief


def _brief(**overrides):
    defaults = dict(
        product="X", value_prop="Y", audience="Z",
        angles=["credibility"], tone="t", cta="c",
        formats=["meta_feed_4x5"],
        output_dir="/tmp/x",
        brand_colors=["#1a1a1a", "#ff0055"],
    )
    defaults.update(overrides)
    return AdBrief(**defaults)


def test_models_registry_has_flux():
    assert "flux-dev" in MODELS
    assert MODELS["flux-dev"].startswith("fal-ai/")


def test_build_prompt_includes_product_and_colors():
    brief = _brief()
    prompt = build_image_prompt(
        brief,
        format_name="meta_feed_4x5",
        variant_copy={"headline": "Test", "body": "B", "cta": "C", "angle": "credibility"},
    )
    assert brief.product in prompt
    assert "#1a1a1a" in prompt or "1a1a1a" in prompt


def test_build_prompt_embeds_aspect():
    brief = _brief()
    prompt = build_image_prompt(
        brief, format_name="meta_feed_4x5",
        variant_copy={"headline": "T", "body": "B", "cta": "C", "angle": "a"},
    )
    # 4:5 aspect should appear in some form
    assert "4:5" in prompt or "4x5" in prompt or "1080x1350" in prompt


def test_estimate_image_cost_nonzero():
    c = estimate_image_cost("flux-dev", n=5)
    assert c > 0
