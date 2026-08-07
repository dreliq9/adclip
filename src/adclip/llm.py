"""Legacy text-provider implementations and compatibility names.

New provider-neutral code should import ``TextGenerationProvider`` from
``adclip.providers.contracts`` and resolve adapters through the registry.
``LLMProvider`` remains an alias so existing modules and integrations continue
to work.
"""

from __future__ import annotations

import json
import os
import re

from adclip.providers.contracts import TextGenerationProvider


LLMProvider = TextGenerationProvider


class AnthropicProvider:
    provider_name = "anthropic"

    def __init__(self, model: str = "claude-sonnet-4-6"):
        from adclip._live_apis import require_live_apis

        require_live_apis("AnthropicProvider")

        import anthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "AnthropicProvider requires ANTHROPIC_API_KEY, which this "
                "project normally does not use. Select another registered "
                "text provider or configure a local OpenAI-compatible endpoint."
            )
        self._client = anthropic.Anthropic()
        self._model = model
        self.model_name = model

    async def generate(self, prompt: str, n: int) -> str:
        del n
        import asyncio

        def _call() -> str:
            msg = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            parts = [
                block.text
                for block in msg.content
                if getattr(block, "type", "") == "text"
            ]
            return "\n".join(parts)

        return await asyncio.to_thread(_call)


class FakeLLMProvider:
    """Deterministic provider for tests. Returns ``n`` scripted candidates."""

    provider_name = "fake"

    def __init__(self, model: str = "fake-v1") -> None:
        self.model_name = model

    async def generate(self, prompt: str, n: int) -> str:
        del prompt
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
    """Delegate text generation to an MCP sampling-capable host."""

    provider_name = "sampling"
    model_name = None

    def __init__(self, session, max_tokens: int = 2048):
        self._session = session
        self._max_tokens = max_tokens

    async def generate(self, prompt: str, n: int) -> str:
        del n
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
            f"Sampling response has unexpected content type: "
            f"{type(content).__name__}"
        )


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_copy_candidates(raw: str) -> list[dict]:
    """Extract candidates from a text response; tolerate prose wrapping."""

    match = _JSON_OBJECT_RE.search(raw)
    if not match:
        raise ValueError(f"No JSON object found in text response: {raw[:200]}")
    obj = json.loads(match.group(0))
    candidates = obj.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError(f"No 'candidates' array in text response: {obj}")
    return candidates


def default_provider() -> TextGenerationProvider:
    """Resolve the configured standalone default through the registry."""

    from adclip.providers.registry import default_text_registry

    return default_text_registry().resolve("default")
