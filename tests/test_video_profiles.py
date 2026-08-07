from adclip.video_gen import build_video_arguments


def test_kling_o3_schema():
    endpoint, args, duration = build_video_arguments(
        "scene",
        model="kling-o3-standard",
        duration=5,
        aspect_ratio="9:16",
        options={"generate_audio": True},
    )
    assert endpoint.endswith("o3/standard/text-to-video")
    assert args["duration"] == "5"
    assert args["aspect_ratio"] == "9:16"
    assert args["generate_audio"] is True
    assert duration == 5.0


def test_veo_duration_normalizes_to_supported_value():
    endpoint, args, duration = build_video_arguments(
        "scene",
        model="veo-3.1",
        duration=5,
        aspect_ratio="9:16",
        options={"resolution": "1080p", "generate_audio": True},
    )
    assert endpoint == "fal-ai/veo3.1"
    assert args["duration"] == "6s"
    assert args["resolution"] == "1080p"
    assert duration == 6.0


def test_seedance_schema():
    endpoint, args, duration = build_video_arguments(
        "three shots",
        model="seedance-2-fast",
        duration=10,
        aspect_ratio="9:16",
        seed=12,
        options={"generate_audio": True},
    )
    assert endpoint == "bytedance/seedance-2.0/fast/text-to-video"
    assert args["duration"] == "10"
    assert args["resolution"] == "720p"
    assert args["seed"] == 12
    assert duration == 10.0


def test_wan_duration_is_five_or_ten():
    _, args, duration = build_video_arguments(
        "scene", model="wan-2.6", duration=8, aspect_ratio="16:9"
    )
    assert args["duration"] == "10"
    assert duration == 10.0
