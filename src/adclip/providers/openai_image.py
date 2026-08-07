"""Direct OpenAI image-generation adapter using the HTTP API contract."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from adclip.formats import get_format


@dataclass(frozen=True)
class OpenAIImageResult:
    local_path: str
    url: str
    model: str
    cost_usd: float


def _images_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/images/generations"):
        return base
    if base.endswith("/v1"):
        return f"{base}/images/generations"
    return f"{base}/v1/images/generations"


def _multiple_of_16(value: int) -> int:
    return max(16, round(value / 16) * 16)


def image_size_for_format(format_name: str) -> str:
    fmt = get_format(format_name)
    width = _multiple_of_16(fmt.width)
    height = _multiple_of_16(fmt.height)
    return f"{width}x{height}"


def estimate_cost_usd(size: str, quality: str) -> float:
    """Conservative per-image estimate scaled from a 1024-square baseline."""

    width_text, height_text = size.lower().split("x", 1)
    pixels = int(width_text) * int(height_text)
    base = {"low": 0.006, "medium": 0.053, "high": 0.211}.get(quality, 0.211)
    return round(base * max(0.5, pixels / (1024 * 1024)), 4)


def generate_image(
    prompt: str,
    *,
    format_name: str,
    output_dir: str,
    seed: int | None = None,
    model: str = "gpt-image-2",
    options: dict[str, object] | None = None,
) -> OpenAIImageResult:
    """Generate one image through OpenAI's first-party Images API."""

    del seed
    from adclip._live_apis import require_live_apis

    require_live_apis("OpenAI image generation")
    api_key = (
        os.environ.get("ADCLIP_OPENAI_IMAGE_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not api_key:
        raise RuntimeError(
            "OpenAI image generation requires ADCLIP_OPENAI_IMAGE_API_KEY "
            "or OPENAI_API_KEY"
        )

    config = dict(options or {})
    quality = str(config.get("quality", "high"))
    output_format = str(config.get("output_format", "png"))
    size = str(config.get("size") or image_size_for_format(format_name))
    body = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "output_format": output_format,
        "n": 1,
    }
    if "background" in config:
        body["background"] = config["background"]

    base_url = os.environ.get("ADCLIP_OPENAI_IMAGE_BASE_URL") or os.environ.get(
        "OPENAI_BASE_URL", "https://api.openai.com"
    )
    request = Request(
        _images_endpoint(base_url),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = float(os.environ.get("ADCLIP_OPENAI_IMAGE_TIMEOUT", "180"))
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(
            f"OpenAI image endpoint returned HTTP {exc.code}: {detail}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            f"OpenAI image endpoint request failed: {exc.reason}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI image endpoint returned invalid JSON") from exc

    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("OpenAI image response did not contain data[]")
    item = data[0]
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    extension = "jpg" if output_format == "jpeg" else output_format
    local = Path(output_dir) / f"{format_name}_openai.{extension}"

    image_url = str(item.get("url") or "")
    encoded = item.get("b64_json")
    if isinstance(encoded, str) and encoded:
        local.write_bytes(base64.b64decode(encoded))
    elif image_url:
        from urllib.request import urlretrieve

        urlretrieve(image_url, str(local))
    else:
        raise RuntimeError("OpenAI image response contained neither b64_json nor url")

    return OpenAIImageResult(
        local_path=str(local),
        url=image_url,
        model=model,
        cost_usd=estimate_cost_usd(size, quality),
    )
