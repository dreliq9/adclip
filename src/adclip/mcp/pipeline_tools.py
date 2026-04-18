"""MCP tool: adclip_generate_variants (full pipeline)."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from adclip.llm import FakeLLMProvider, default_provider
from adclip.pipeline import run_pipeline
from adclip.schema import AdBrief


def _fake_image_fn(prompt, *, format_name, output_dir, seed):
    from PIL import Image

    from adclip.formats import get_format

    fmt = get_format(format_name)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = Path(output_dir) / f"{format_name}_{seed or 'x'}.png"
    Image.new("RGB", (fmt.width, fmt.height), color=(20, 20, 40)).save(path)

    class R:
        local_path = str(path)
        url = ""
        model = "flux-fake"
        cost_usd = 0.0

    return R()


def _generate_variants_impl(
    brief_json: str,
    *,
    llm_provider: str = "default",
    image_provider: str = "default",
) -> dict:
    try:
        brief = AdBrief(**json.loads(brief_json))
    except (ValidationError, ValueError, json.JSONDecodeError) as e:
        return {"ok": False, "error": str(e)}

    llm = FakeLLMProvider() if llm_provider == "fake" else default_provider()
    img_fn = _fake_image_fn if image_provider == "fake" else None

    return run_pipeline(brief, llm_provider=llm, image_fn=img_fn)


def register(mcp) -> None:
    @mcp.tool()
    def adclip_generate_variants(
        brief_json: str,
        llm_provider: str = "default",
        image_provider: str = "default",
    ) -> str:
        """Run the full pipeline: copy -> policy -> image -> compose -> render.

        Args:
            brief_json: JSON-encoded AdBrief.
            llm_provider: 'default' (Anthropic) or 'fake' (tests).
            image_provider: 'default' (fal.ai Flux) or 'fake' (tests).
        """
        return json.dumps(_generate_variants_impl(
            brief_json,
            llm_provider=llm_provider,
            image_provider=image_provider,
        ))
