"""Task-oriented image and video model routing.

The route catalog is deliberately separate from provider adapters. A route
expresses the kind of creative work being requested, the currently preferred
provider/model pair, safe generation options, and ordered fallbacks. It does
not execute a model or silently retry paid calls.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal, Mapping


MediaModality = Literal["image", "video"]


@dataclass(frozen=True)
class RouteTarget:
    """One provider/model candidate within a media route."""

    provider: str
    model: str
    options: Mapping[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "options": dict(self.options),
        }


@dataclass(frozen=True)
class MediaRoute:
    """A named task policy for one media modality."""

    name: str
    modality: MediaModality
    description: str
    primary: RouteTarget
    fallbacks: tuple[RouteTarget, ...] = ()
    requires: tuple[str, ...] = ()
    production_ready: bool = True

    def target_for_provider(self, provider: str) -> RouteTarget | None:
        for target in (self.primary, *self.fallbacks):
            if target.provider == provider:
                return target
        return None

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "modality": self.modality,
            "description": self.description,
            "primary": self.primary.as_dict(),
            "fallbacks": [target.as_dict() for target in self.fallbacks],
            "requires": list(self.requires),
            "production_ready": self.production_ready,
        }


IMAGE_ROUTES: dict[str, MediaRoute] = {
    "general": MediaRoute(
        name="general",
        modality="image",
        description=(
            "General marketing creative with strong instruction following, "
            "layout reasoning, and typography."
        ),
        primary=RouteTarget(
            "fal",
            "gpt-image-2",
            {"quality": "medium", "output_format": "png"},
        ),
        fallbacks=(
            RouteTarget("fal", "nano-banana-2", {"resolution": "1K"}),
            RouteTarget("fal", "flux-2-pro", {}),
        ),
    ),
    "premium": MediaRoute(
        name="premium",
        modality="image",
        description="Highest-quality general marketing image through first-party OpenAI.",
        primary=RouteTarget(
            "openai",
            "gpt-image-2",
            {"quality": "high", "output_format": "png"},
        ),
        fallbacks=(
            RouteTarget(
                "fal",
                "gpt-image-2",
                {"quality": "high", "output_format": "png"},
            ),
            RouteTarget("fal", "flux-2-max", {}),
        ),
    ),
    "text-heavy": MediaRoute(
        name="text-heavy",
        modality="image",
        description="Posters, infographics, packaging, UI, and readable in-image text.",
        primary=RouteTarget(
            "fal",
            "gpt-image-2",
            {"quality": "high", "output_format": "png"},
        ),
        fallbacks=(
            RouteTarget("fal", "nano-banana-pro", {"resolution": "2K"}),
            RouteTarget("fal", "flux-2-flex", {}),
        ),
    ),
    "reference": MediaRoute(
        name="reference",
        modality="image",
        description="Reference-preserving product, person, or campaign-series editing.",
        primary=RouteTarget("fal", "nano-banana-2", {"resolution": "2K"}),
        fallbacks=(
            RouteTarget("fal", "gpt-image-2", {"quality": "high"}),
        ),
        requires=("reference_images",),
        production_ready=False,
    ),
    "bulk": MediaRoute(
        name="bulk",
        modality="image",
        description="Cost-controlled production batches with strong compositional control.",
        primary=RouteTarget("fal", "flux-2-pro", {}),
        fallbacks=(
            RouteTarget("fal", "nano-banana-2-lite", {}),
            RouteTarget("fal", "flux-2", {}),
        ),
    ),
    "draft": MediaRoute(
        name="draft",
        modality="image",
        description="Fast inexpensive concept drafts before premium rendering.",
        primary=RouteTarget("fal", "nano-banana-2-lite", {}),
        fallbacks=(RouteTarget("fal", "flux-2", {}),),
    ),
    "brand-control": MediaRoute(
        name="brand-control",
        modality="image",
        description="Exact palettes, controlled layouts, and design-system consistency.",
        primary=RouteTarget("fal", "flux-2-flex", {}),
        fallbacks=(
            RouteTarget("fal", "gpt-image-2", {"quality": "high"}),
            RouteTarget("fal", "flux-2-pro", {}),
        ),
    ),
    "vector": MediaRoute(
        name="vector",
        modality="image",
        description="Editable vector illustration, iconography, or logo exploration.",
        primary=RouteTarget("recraft", "recraft-v4.1-vector", {}),
        requires=("vector_output", "recraft_adapter"),
        production_ready=False,
    ),
}


VIDEO_ROUTES: dict[str, MediaRoute] = {
    "general": MediaRoute(
        name="general",
        modality="video",
        description="Practical general-purpose social and performance-ad video.",
        primary=RouteTarget(
            "fal",
            "kling-o3-standard",
            {"duration": 5, "generate_audio": False},
        ),
        fallbacks=(
            RouteTarget(
                "fal",
                "kling-3-standard",
                {"duration": 5, "generate_audio": False},
            ),
            RouteTarget(
                "fal",
                "wan-2.7",
                {"duration": 5, "resolution": "720p"},
            ),
        ),
    ),
    "premium": MediaRoute(
        name="premium",
        modality="video",
        description="Premium cinematic output with native audio and dialogue.",
        primary=RouteTarget(
            "fal",
            "veo-3.1",
            {"duration": 8, "resolution": "1080p", "generate_audio": True},
        ),
        fallbacks=(
            RouteTarget(
                "fal",
                "kling-o3-standard",
                {"duration": 8, "generate_audio": True},
            ),
        ),
    ),
    "multi-shot": MediaRoute(
        name="multi-shot",
        modality="video",
        description="Directed multi-shot stories and camera-controlled sequences.",
        primary=RouteTarget(
            "fal",
            "seedance-2-fast",
            {"duration": 10, "resolution": "720p", "generate_audio": True},
        ),
        fallbacks=(
            RouteTarget(
                "fal",
                "kling-o3-standard",
                {"duration": 10, "generate_audio": True, "shot_type": "intelligent"},
            ),
        ),
    ),
    "multi-reference": MediaRoute(
        name="multi-reference",
        modality="video",
        description="Video directed by multiple image, video, and audio references.",
        primary=RouteTarget(
            "fal",
            "seedance-2-reference",
            {"duration": "auto", "resolution": "720p", "generate_audio": True},
        ),
        requires=("reference_media",),
        production_ready=False,
    ),
    "budget": MediaRoute(
        name="budget",
        modality="video",
        description="Lower-cost video exploration and high-volume social variants.",
        primary=RouteTarget(
            "fal",
            "wan-2.7",
            {"duration": 5, "resolution": "720p"},
        ),
        fallbacks=(
            RouteTarget(
                "fal",
                "kling-o3-standard",
                {"duration": 5, "generate_audio": False},
            ),
            RouteTarget(
                "fal",
                "wan-2.6",
                {"duration": 5, "resolution": "720p"},
            ),
        ),
    ),
    "image-animation": MediaRoute(
        name="image-animation",
        modality="video",
        description="Animate an approved still while preserving its composition.",
        primary=RouteTarget(
            "fal",
            "kling-o3-standard-i2v",
            {"duration": 5, "generate_audio": False},
        ),
        requires=("start_image",),
        production_ready=False,
    ),
    "edit": MediaRoute(
        name="edit",
        modality="video",
        description="Transform or repair existing footage while preserving continuity.",
        primary=RouteTarget("runway", "aleph-2", {}),
        requires=("source_video", "runway_adapter"),
        production_ready=False,
    ),
}


ROUTES: dict[MediaModality, dict[str, MediaRoute]] = {
    "image": IMAGE_ROUTES,
    "video": VIDEO_ROUTES,
}


def default_route_name(modality: MediaModality) -> str:
    env_name = "ADCLIP_IMAGE_ROUTE" if modality == "image" else "ADCLIP_VIDEO_ROUTE"
    return os.environ.get(env_name, "general")


def get_media_route(
    modality: MediaModality,
    name: str | None = None,
) -> MediaRoute:
    route_name = default_route_name(modality) if name in {None, "default"} else name
    try:
        return ROUTES[modality][route_name]
    except KeyError as exc:
        known = ", ".join(sorted(ROUTES[modality]))
        raise ValueError(
            f"Unknown {modality} route {route_name!r}. Known routes: {known}"
        ) from exc


def list_media_routes(modality: MediaModality | None = None) -> list[dict[str, object]]:
    modalities: tuple[MediaModality, ...] = (
        (modality,) if modality is not None else ("image", "video")
    )
    return [
        ROUTES[current][name].as_dict()
        for current in modalities
        for name in sorted(ROUTES[current])
    ]


def recommend_media_route(
    modality: MediaModality,
    *,
    text_heavy: bool = False,
    reference_images: int = 0,
    reference_media: int = 0,
    existing_video: bool = False,
    vector_output: bool = False,
    premium: bool = False,
    high_volume: bool = False,
    draft: bool = False,
    multi_shot: bool = False,
    brand_control: bool = False,
) -> MediaRoute:
    """Choose a route from explicit, inspectable creative requirements."""

    if modality == "image":
        if vector_output:
            return IMAGE_ROUTES["vector"]
        if reference_images:
            return IMAGE_ROUTES["reference"]
        if text_heavy:
            return IMAGE_ROUTES["text-heavy"]
        if brand_control:
            return IMAGE_ROUTES["brand-control"]
        if premium:
            return IMAGE_ROUTES["premium"]
        if draft:
            return IMAGE_ROUTES["draft"]
        if high_volume:
            return IMAGE_ROUTES["bulk"]
        return IMAGE_ROUTES["general"]

    if existing_video:
        return VIDEO_ROUTES["edit"]
    if reference_media:
        return VIDEO_ROUTES["multi-reference"]
    if multi_shot:
        return VIDEO_ROUTES["multi-shot"]
    if premium:
        return VIDEO_ROUTES["premium"]
    if high_volume or draft:
        return VIDEO_ROUTES["budget"]
    return VIDEO_ROUTES["general"]


def ensure_route_executable(route: MediaRoute) -> None:
    """Reject routes whose required inputs/adapters are not wired yet."""

    if route.production_ready:
        return
    requirements = ", ".join(route.requires) or "additional capabilities"
    raise RuntimeError(
        f"{route.modality} route {route.name!r} is cataloged but not executable "
        f"in the current pipeline; it requires: {requirements}."
    )
