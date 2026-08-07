import pytest

from adclip.model_routing import (
    get_media_route,
    list_media_routes,
    recommend_media_route,
)
from adclip.providers.media import resolve_image_provider
from adclip.runtime import RuntimeMode, RuntimePolicy


def test_general_routes_use_new_defaults():
    image = get_media_route("image", "general")
    video = get_media_route("video", "general")
    assert image.primary.as_dict()["model"] == "gpt-image-2"
    assert image.primary.as_dict()["options"]["quality"] == "medium"
    assert video.primary.as_dict()["model"] == "kling-o3-standard"


def test_recommender_is_task_specific():
    assert recommend_media_route("image", text_heavy=True).name == "text-heavy"
    assert recommend_media_route("image", high_volume=True).name == "bulk"
    assert recommend_media_route("video", premium=True).name == "premium"
    assert recommend_media_route("video", multi_shot=True).name == "multi-shot"


def test_unwired_routes_are_discoverable_but_not_executable():
    route = get_media_route("image", "reference")
    assert route.production_ready is False
    with pytest.raises(RuntimeError, match="reference_images"):
        resolve_image_provider(
            route="reference",
            policy=RuntimePolicy(mode=RuntimeMode.ONLINE),
        )


def test_explicit_model_overrides_route_primary():
    binding = resolve_image_provider(
        "fake",
        route="text-heavy",
        model="fixture-image",
        policy=RuntimePolicy(mode=RuntimeMode.OFFLINE),
    )
    assert binding.as_dict() == {"provider": "fake", "model": "fixture-image"}
    assert binding.provenance()["route"] == "text-heavy"


def test_media_catalog_includes_fallbacks_without_auto_retry():
    routes = list_media_routes("image")
    general = next(route for route in routes if route["name"] == "general")
    assert general["fallbacks"]
