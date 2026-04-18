"""LLM copy generation. Pluggable provider interface.

Default provider: Anthropic Claude (via anthropic SDK).
Fake provider: deterministic, for tests.
"""

from __future__ import annotations

import json
import os
import re
from typing import Protocol


class LLMProvider(Protocol):
    def generate(self, prompt: str, n: int) -> str:
        """Return raw text containing a JSON block with `candidates` array."""
        ...


class AnthropicProvider:
    def __init__(self, model: str = "claude-sonnet-4-6"):
        import anthropic

        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self._client = anthropic.Anthropic()
        self._model = model

    def generate(self, prompt: str, n: int) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        # Block returned is a list of content blocks — join text blocks.
        parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
        return "\n".join(parts)


class FakeLLMProvider:
    """Deterministic provider for tests. Returns n scripted candidates."""

    def generate(self, prompt: str, n: int) -> str:
        candidates = [
            {
                "headline": f"Headline {i+1}",
                "body": f"Body text {i+1} for the test.",
                "cta": f"CTA {i+1}",
            }
            for i in range(n)
        ]
        return json.dumps({"candidates": candidates})


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
    """Return the default provider based on env config."""
    return AnthropicProvider()
