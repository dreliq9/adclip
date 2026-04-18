"""Ad format catalog — platform specs as of 2026-04.

Sources:
- Meta ad specs: https://www.facebook.com/business/ads-guide
- Google RSA: https://support.google.com/google-ads/answer/7684791
- March 2026: Meta unified FB/IG Stories + Reels into a single 9:16 safe zone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AdFormatSpec:
    name: str
    aspect: str                          # "1:1", "4:5", "9:16", "16:9", "1.91:1", or "text"
    width: int                           # 0 for text-only
    height: int                          # 0 for text-only
    kind: Literal["static", "video", "text"]
    headline_max: int                    # char limit for primary headline/overlay
    body_max: int                        # char limit for body/description
    # RSA-specific (text ads that accept multiple pooled headlines/descriptions)
    rsa_max_headlines: int = 0
    rsa_max_descriptions: int = 0
    rsa_min_headlines: int = 0
    rsa_min_descriptions: int = 0
    # Optional: platform loudness target for video (LUFS)
    lufs_target: float | None = None


FORMATS: dict[str, AdFormatSpec] = {
    "meta_feed_1x1": AdFormatSpec(
        name="meta_feed_1x1",
        aspect="1:1",
        width=1080, height=1080,
        kind="static",
        headline_max=40, body_max=125,
    ),
    "meta_feed_4x5": AdFormatSpec(
        name="meta_feed_4x5",
        aspect="4:5",
        width=1080, height=1350,
        kind="static",
        headline_max=40, body_max=125,
    ),
    "stories_reels_9x16": AdFormatSpec(
        name="stories_reels_9x16",
        aspect="9:16",
        width=1080, height=1920,
        kind="video",
        headline_max=10, body_max=125,  # 10 is overlay limit on Reels
        lufs_target=-14.0,
    ),
    "google_rsa": AdFormatSpec(
        name="google_rsa",
        aspect="text", width=0, height=0,
        kind="text",
        headline_max=30, body_max=90,
        rsa_max_headlines=15, rsa_max_descriptions=4,
        rsa_min_headlines=3, rsa_min_descriptions=2,
    ),
    "google_display_square": AdFormatSpec(
        name="google_display_square",
        aspect="1:1",
        width=1200, height=1200,
        kind="static",
        headline_max=30, body_max=90,
    ),
    "google_display_landscape": AdFormatSpec(
        name="google_display_landscape",
        aspect="1.91:1",
        width=1200, height=628,
        kind="static",
        headline_max=30, body_max=90,
    ),
    "tiktok_9x16": AdFormatSpec(
        name="tiktok_9x16",
        aspect="9:16",
        width=1080, height=1920,
        kind="video",
        headline_max=100, body_max=0,
        lufs_target=-14.0,
    ),
    "youtube_shorts_9x16": AdFormatSpec(
        name="youtube_shorts_9x16",
        aspect="9:16",
        width=1080, height=1920,
        kind="video",
        headline_max=100, body_max=0,
        lufs_target=-14.0,
    ),
    "linkedin_single": AdFormatSpec(
        name="linkedin_single",
        aspect="1.91:1",
        width=1200, height=627,
        kind="static",
        headline_max=70, body_max=600,
    ),
    "x_promoted": AdFormatSpec(
        name="x_promoted",
        aspect="16:9",
        width=1200, height=675,
        kind="static",
        headline_max=280, body_max=0,
    ),
}


def get_format(name: str) -> AdFormatSpec:
    """Look up a format spec by name. Raises KeyError if unknown."""
    if name not in FORMATS:
        raise KeyError(f"Unknown ad format: {name!r}. Known: {sorted(FORMATS)}")
    return FORMATS[name]
