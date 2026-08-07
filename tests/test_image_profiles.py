from adclip.image_gen import build_generation_arguments, resolve_model_endpoint


def test_gpt_image_2_uses_quality_and_multiple_of_16_dimensions():
    args = build_generation_arguments(
        "hello",
        format_name="meta_feed_4x5",
        model="gpt-image-2",
        options={"quality": "high"},
    )
    assert args["quality"] == "high"
    assert args["image_size"]["width"] % 16 == 0
    assert args["image_size"]["height"] % 16 == 0
    assert "seed" not in args


def test_nano_banana_uses_aspect_and_resolution_not_pixel_object():
    args = build_generation_arguments(
        "hello",
        format_name="meta_feed_4x5",
        model="nano-banana-2",
        seed=7,
        options={"resolution": "2K"},
    )
    assert args["aspect_ratio"] == "4:5"
    assert args["resolution"] == "2K"
    assert args["seed"] == 7
    assert "image_size" not in args


def test_flux_2_uses_pixel_dimensions_and_seed():
    args = build_generation_arguments(
        "hello",
        format_name="meta_feed_1x1",
        model="flux-2-pro",
        seed=4,
    )
    assert args["image_size"] == {"width": 1088, "height": 1088}
    assert args["seed"] == 4


def test_raw_endpoint_infers_family():
    assert resolve_model_endpoint("fal-ai/custom/flux-model") == "fal-ai/custom/flux-model"
