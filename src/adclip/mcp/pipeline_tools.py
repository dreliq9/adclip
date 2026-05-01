"""MCP tool: adclip_generate_variants (full pipeline)."""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import Context
from pydantic import ValidationError

from adclip.llm import (
    FakeLLMProvider,
    LLMProvider,
    SamplingLLMProvider,
)
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


def _fake_video_fn(prompt, *, format_name, output_dir, seed):
    """Synthesize a 1-second test mp4 via FFmpeg lavfi for tests."""
    import subprocess

    from adclip.formats import get_format

    fmt = get_format(format_name)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = Path(output_dir) / f"{format_name}_{seed or 'x'}_raw.mp4"
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"testsrc=duration=1:size={fmt.width}x{fmt.height}:rate=30",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    class R:
        local_path = str(path)
        url = ""
        model = "kling-fake"
        cost_usd = 0.0
        duration = 1.0

    return R()


def _resolve_llm(name: str, session) -> LLMProvider:
    if name == "fake":
        return FakeLLMProvider()
    if name == "default" or name == "claude-cli":
        from adclip.claude_cli import ClaudeCliProvider
        return ClaudeCliProvider()
    if name == "sampling":
        if session is None:
            raise RuntimeError(
                "sampling provider requires an MCP session. Use "
                "llm_provider='claude-cli' (the default) if no "
                "sampling-capable client is connected."
            )
        return SamplingLLMProvider(session)
    if name == "anthropic":
        from adclip.llm import AnthropicProvider
        return AnthropicProvider()
    raise ValueError(f"Unknown llm_provider: {name}")


async def _generate_variants_impl(
    brief_json: str,
    *,
    llm_provider: str = "default",
    image_provider: str = "default",
    video_provider: str = "default",
    session=None,
) -> dict:
    try:
        brief = AdBrief(**json.loads(brief_json))
    except (ValidationError, ValueError, json.JSONDecodeError) as e:
        return {"ok": False, "error": str(e)}

    try:
        llm = _resolve_llm(llm_provider, session)
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

    img_fn = _fake_image_fn if image_provider == "fake" else None
    vid_fn = _fake_video_fn if video_provider == "fake" else None

    return await run_pipeline(
        brief, llm_provider=llm, image_fn=img_fn, video_fn=vid_fn,
    )


def register(mcp) -> None:
    @mcp.tool()
    async def adclip_generate_variants(
        brief_json: str,
        ctx: Context,
        llm_provider: str = "default",
        image_provider: str = "default",
        video_provider: str = "default",
    ) -> str:
        """Run the full pipeline: copy -> policy -> image -> compose -> render.

        Args:
            brief_json: JSON-encoded AdBrief.
            llm_provider: 'default'/'claude-cli' (shells out to claude CLI —
                no key, works under any MCP client), 'sampling' (asks
                Claude via MCP sampling — only works under clients that
                implement it), 'anthropic' (direct API key), or 'fake'
                (tests).
            image_provider: 'default' (fal.ai Flux) or 'fake' (tests).
            video_provider: 'default' (fal.ai via declip) or 'fake' (tests).
        """
        session = ctx.request_context.session
        result = await _generate_variants_impl(
            brief_json,
            llm_provider=llm_provider,
            image_provider=image_provider,
            video_provider=video_provider,
            session=session,
        )
        return json.dumps(result)
