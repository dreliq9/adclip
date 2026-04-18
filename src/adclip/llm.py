"""LLM copy generation. Pluggable async provider interface.

Providers:
- SamplingLLMProvider: delegates to the calling MCP client (Claude Code)
  via MCP's sampling/createMessage. No API key required on adclip's side.
  This is the default when running as an MCP server.
- AnthropicProvider: direct Anthropic API call. Requires ANTHROPIC_API_KEY.
  Use for CLI/standalone mode without a sampling-capable MCP host.
- FakeLLMProvider: deterministic, for tests.
"""

from __future__ import annotations

import json
import os
import re
from typing import Protocol


class LLMProvider(Protocol):
    async def generate(self, prompt: str, n: int) -> str:
        """Return raw text containing a JSON block with `candidates` array."""
        ...


class AnthropicProvider:
    def __init__(self, model: str = "claude-sonnet-4-6"):
        import anthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self._client = anthropic.Anthropic()
        self._model = model

    async def generate(self, prompt: str, n: int) -> str:
        # anthropic SDK call is sync; run in the default thread pool.
        import asyncio

        def _call() -> str:
            msg = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
            return "\n".join(parts)

        return await asyncio.to_thread(_call)


class FakeLLMProvider:
    """Deterministic provider for tests. Returns n scripted candidates."""

    async def generate(self, prompt: str, n: int) -> str:
        candidates = [
            {
                "headline": f"Headline {i+1}",
                "body": f"Body text {i+1} for the test.",
                "cta": f"CTA {i+1}",
            }
            for i in range(n)
        ]
        return json.dumps({"candidates": candidates})


class SamplingLLMProvider:
    """Delegate LLM calls back to the MCP client via sampling/createMessage.

    adclip never talks to an LLM API directly in this mode — it asks the
    calling client (e.g. Claude Code) to run the completion. No API key.
    """

    def __init__(self, session, max_tokens: int = 2048):
        # session: mcp.server.session.ServerSession (from ctx.request_context.session)
        self._session = session
        self._max_tokens = max_tokens

    async def generate(self, prompt: str, n: int) -> str:
        from mcp import types

        result = await self._session.create_message(
            messages=[
                types.SamplingMessage(
                    role="user",
                    content=types.TextContent(type="text", text=prompt),
                ),
            ],
            max_tokens=self._max_tokens,
            system_prompt=(
                "You are an expert performance-ad copywriter. "
                "Respond with JSON only, no prose before or after."
            ),
        )
        content = result.content
        if getattr(content, "type", "") == "text":
            return content.text
        raise RuntimeError(
            f"Sampling response has unexpected content type: {type(content).__name__}"
        )


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_copy_candidates(raw: str) -> list[dict]:
    """Extract candidates array from an LLM response. Tolerates prose wrapping."""
    match = _JSON_OBJECT_RE.search(raw)
    if not match:
        raise ValueError(f"No JSON object found in LLM response: {raw[:200]}")
    obj = json.loads(match.group(0))
    cands = obj.get("candidates")
    if not isinstance(cands, list):
        raise ValueError(f"No 'candidates' array in LLM response: {obj}")
    return cands


def default_provider() -> LLMProvider:
    """Return the default non-MCP provider (CLI / standalone use)."""
    return AnthropicProvider()
