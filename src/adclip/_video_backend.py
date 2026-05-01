"""Vendored slice from declip — fal.ai model catalog + loudnorm.

Kept private (leading underscore) so the surface stays internal. When
declip's `fetch_models.py` or `ops.loudnorm` change in a way we want to
adopt, sync the relevant section here. Sync triggers we expect:

- fal.ai redesigns its /explore page (breaks `_CARD_PATTERN`)
- New model families ship (Kling/Wan/Veo/Sora successors) and we want
  hardcoded aliases beyond the live-fetched catalog
- declip refines the loudnorm two-pass logic

Source of truth: ~/Desktop/mcps/declip/src/declip/{fetch_models,ops}.py.
"""
from __future__ import annotations

import html as html_mod
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Model catalog (vendored from declip.fetch_models)
# ---------------------------------------------------------------------------

CACHE_DIR = Path(os.environ.get("ADCLIP_CACHE_DIR") or (Path.home() / ".cache" / "adclip"))
CACHE_PATH = CACHE_DIR / "fal_models.json"
SOURCE_URL = "https://fal.ai/explore/models"
TTL_SECONDS = 24 * 60 * 60

ALIASES: dict[str, str] = {
    # Kling 3
    "kling-3":         "fal-ai/kling-video/v3/standard/text-to-video",
    "kling-3-pro":     "fal-ai/kling-video/v3/pro/text-to-video",
    "kling-3-i2v":     "fal-ai/kling-video/v3/standard/image-to-video",
    "kling-3-i2v-pro": "fal-ai/kling-video/v3/pro/image-to-video",
    # Kling 2.6
    "kling-2.6":       "fal-ai/kling-video/v2.6/standard/text-to-video",
    "kling-2.6-pro":   "fal-ai/kling-video/v2.6/pro/text-to-video",
    "kling-2.6-i2v":   "fal-ai/kling-video/v2.6/standard/image-to-video",
    # Wan
    "wan-2.6":         "fal-ai/wan/v2.6/text-to-video",
    "wan-2.6-i2v":     "fal-ai/wan/v2.6/image-to-video",
    "wan-2.5":         "fal-ai/wan-25-preview/text-to-video",
    "wan-2.5-i2v":     "fal-ai/wan-25-preview/image-to-video",
    # Budget / open-source
    "ltx":             "fal-ai/ltx-video-v097",
    "luma":            "fal-ai/luma-dream-machine/ray-2",
    "luma-flash":      "fal-ai/luma-dream-machine/ray-2-flash",
    # Premium / latest
    "veo-3":           "fal-ai/veo3",
    "veo-3.1":         "fal-ai/veo3.1",
    "veo-3.1-fast":    "fal-ai/veo3.1/fast",
    "sora-2":          "fal-ai/sora-2/text-to-video",
    "sora-2-pro":      "fal-ai/sora-2/text-to-video/pro",
}

MODEL_COST_PER_SEC: dict[str, float] = {
    "fal-ai/kling-video/v3/standard/text-to-video":   0.17,
    "fal-ai/kling-video/v3/pro/text-to-video":        0.22,
    "fal-ai/kling-video/v3/standard/image-to-video":  0.17,
    "fal-ai/kling-video/v3/pro/image-to-video":       0.22,
    "fal-ai/kling-video/v2.6/standard/text-to-video": 0.07,
    "fal-ai/kling-video/v2.6/pro/text-to-video":      0.14,
    "fal-ai/kling-video/v2.6/standard/image-to-video": 0.07,
    "fal-ai/wan/v2.6/text-to-video":                  0.06,
    "fal-ai/wan/v2.6/image-to-video":                 0.06,
    "fal-ai/wan-25-preview/text-to-video":            0.05,
    "fal-ai/wan-25-preview/image-to-video":           0.05,
    "fal-ai/ltx-video-v097":                          0.008,
    "fal-ai/luma-dream-machine/ray-2":                0.10,
    "fal-ai/luma-dream-machine/ray-2-flash":          0.04,
    "fal-ai/veo3":                                    0.40,
    "fal-ai/veo3.1":                                  0.30,
    "fal-ai/veo3.1/fast":                             0.10,
    "fal-ai/sora-2/text-to-video":                    0.30,
    "fal-ai/sora-2/text-to-video/pro":                0.50,
}

BUNDLED_FALLBACK_ENDPOINTS: tuple[str, ...] = tuple(ALIASES.values())


@dataclass
class ModelInfo:
    endpoint: str
    name: str
    description: str
    is_video: bool


def _is_video_endpoint(endpoint: str) -> bool:
    e = endpoint.lower()
    if any(seg in e for seg in (
        "text-to-video", "image-to-video", "video-to-video",
        "first-last-frame-to-video", "reference-to-video",
    )):
        return True
    for root in (
        "fal-ai/veo3", "fal-ai/veo2",
        "fal-ai/ltx-video", "fal-ai/luma-dream-machine",
        "fal-ai/sora-2",
    ):
        if e == root or e.startswith(root + "/"):
            return True
    return False


_CARD_PATTERN = re.compile(
    r'<a\s+class="page-model-card[^"]*"\s+href="/models/([a-z0-9][a-z0-9._/-]+)"'
    r'(.*?)</a>',
    re.DOTALL,
)
_IMG_ALT_PATTERN = re.compile(r'<img\s+alt="([^"]*)"')


def _parse_html(html: str) -> list[ModelInfo]:
    seen: dict[str, ModelInfo] = {}
    for endpoint, body in _CARD_PATTERN.findall(html):
        if endpoint in seen:
            continue
        alt_match = _IMG_ALT_PATTERN.search(body)
        raw_description = alt_match.group(1) if alt_match else ""
        description = html_mod.unescape(raw_description).strip()
        name = endpoint.split("/", 1)[1] if "/" in endpoint else endpoint
        seen[endpoint] = ModelInfo(
            endpoint=endpoint,
            name=name,
            description=description,
            is_video=_is_video_endpoint(endpoint),
        )
    return list(seen.values())


def _http_get(url: str, timeout: float = 10.0) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "adclip-fetch-models/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _read_cache() -> dict | None:
    if not CACHE_PATH.exists():
        return None
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(CACHE_PATH)


def fetch_models(force_refresh: bool = False) -> list[ModelInfo]:
    """Return the catalog. Falls back gracefully on network/parse failure."""
    cache = _read_cache()
    cache_fresh = (
        cache is not None
        and isinstance(cache.get("fetched_at"), (int, float))
        and (time.time() - cache["fetched_at"]) < TTL_SECONDS
    )
    if not force_refresh and cache_fresh:
        return [ModelInfo(**m) for m in cache["models"]]

    try:
        html = _http_get(SOURCE_URL)
        models = _parse_html(html)
        if models:
            _write_cache({
                "fetched_at": time.time(),
                "source_url": SOURCE_URL,
                "models": [asdict(m) for m in models],
            })
            return models
    except (urllib.error.URLError, TimeoutError, OSError):
        pass

    if cache is not None and cache.get("models"):
        return [ModelInfo(**m) for m in cache["models"]]

    return [
        ModelInfo(
            endpoint=ep,
            name=ep.split("/", 1)[1] if "/" in ep else ep,
            description="(bundled fallback - live fetch and cache both unavailable)",
            is_video=_is_video_endpoint(ep),
        )
        for ep in BUNDLED_FALLBACK_ENDPOINTS
    ]


def resolve_endpoint(name_or_endpoint: str) -> str:
    """Resolve a short alias to a canonical endpoint, or return input unchanged."""
    return ALIASES.get(name_or_endpoint, name_or_endpoint)


def cost_per_sec(name_or_endpoint: str) -> float | None:
    """Look up per-second cost. Accepts alias or endpoint. None if unknown."""
    endpoint = resolve_endpoint(name_or_endpoint)
    return MODEL_COST_PER_SEC.get(endpoint)


def to_image_to_video(endpoint: str) -> str:
    """Rewrite a text-to-video endpoint to its image-to-video sibling."""
    if "/text-to-video" in endpoint:
        return endpoint.replace("/text-to-video", "/image-to-video")
    return endpoint


def cache_status() -> dict:
    cache = _read_cache()
    if cache is None:
        return {"cached": False, "path": str(CACHE_PATH)}
    age = time.time() - cache.get("fetched_at", 0)
    return {
        "cached": True,
        "path": str(CACHE_PATH),
        "fetched_at": cache.get("fetched_at"),
        "age_seconds": int(age),
        "fresh": age < TTL_SECONDS,
        "model_count": len(cache.get("models", [])),
        "source_url": cache.get("source_url"),
    }


# ---------------------------------------------------------------------------
# Loudness normalization (vendored from declip.ops.loudnorm)
# ---------------------------------------------------------------------------

LOUDNORM_TARGETS = {
    "youtube": -14.0, "shorts": -14.0,
    "tiktok": -11.0, "reels": -11.0, "instagram": -11.0,
    "podcast": -16.0, "broadcast": -23.0,
}


def _run(cmd: list[str], timeout: int = 300) -> tuple[bool, str]:
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        return False, proc.stderr.decode(errors="replace")[-500:]
    return True, ""


def _file_info(path: str) -> str:
    p = Path(path)
    if p.exists():
        return f"{path} ({p.stat().st_size / 1024 / 1024:.1f} MB)"
    return path


def _output_path(input_file: str, output: str | None, suffix: str) -> str:
    if output:
        return output
    p = Path(input_file)
    if suffix.startswith("."):
        return str(p.with_suffix(suffix))
    return str(p.with_stem(p.stem + suffix))


def resolve_loudnorm_target(target: str) -> tuple[float | None, str | None]:
    """Resolve a target name or number to LUFS. Returns (lufs, error)."""
    lufs = LOUDNORM_TARGETS.get(target.lower())
    if lufs is not None:
        return lufs, None
    try:
        return float(target), None
    except ValueError:
        return None, (
            f"Invalid target '{target}'. Use youtube, tiktok, podcast, "
            "broadcast, or a LUFS number like -14"
        )


def loudnorm(
    input_file: str,
    target: str = "youtube",
    output_path: str | None = None,
) -> tuple[bool, str]:
    """Two-pass EBU R128 loudness normalization."""
    if not Path(input_file).exists():
        return False, f"Error: {input_file} not found"

    target_lufs, err = resolve_loudnorm_target(target)
    if err:
        return False, f"Error: {err}"

    out = _output_path(input_file, output_path, "_loudnorm")
    tp = -1.5

    cmd1 = [
        "ffmpeg", "-y", "-i", input_file,
        "-af", f"loudnorm=I={target_lufs}:TP={tp}:LRA=11:print_format=json",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd1, capture_output=True, text=True, timeout=600)

    stderr = proc.stderr
    json_start = stderr.rfind("{")
    json_end = stderr.rfind("}") + 1
    measured = {}
    if json_start >= 0 and json_end > json_start:
        try:
            measured = json.loads(stderr[json_start:json_end])
        except json.JSONDecodeError:
            pass

    if not measured:
        return False, "Error: could not measure loudness in pass 1"

    af = (
        f"loudnorm=I={target_lufs}:TP={tp}:LRA=11:"
        f"measured_I={measured.get('input_i', '-24.0')}:"
        f"measured_TP={measured.get('input_tp', '-2.0')}:"
        f"measured_LRA={measured.get('input_lra', '7.0')}:"
        f"measured_thresh={measured.get('input_thresh', '-34.0')}:"
        f"offset={measured.get('target_offset', '0.0')}:linear=true"
    )

    cmd2 = ["ffmpeg", "-y", "-i", input_file, "-af", af,
            "-c:v", "copy", out]
    ok, err = _run(cmd2, timeout=600)
    if not ok:
        return False, err
    return True, f"Normalized to {target_lufs:.0f} LUFS ({target}): {_file_info(out)}"
