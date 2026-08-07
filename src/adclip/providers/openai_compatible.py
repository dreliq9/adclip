"""Generic OpenAI-compatible text provider.

This adapter intentionally depends only on the HTTP contract, not the OpenAI
Python SDK. It works with local servers and gateways that implement
``/v1/chat/completions`` as well as hosted compatible endpoints.
"""

from __future__ import annotations

import asyncio
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from adclip.runtime import (
    ProviderRequirements,
    RuntimePolicy,
    endpoint_is_loopback,
)


class OpenAICompatibleProvider:
    """Text provider for a configurable OpenAI-compatible chat endpoint."""

    provider_name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 90.0,
        system_prompt: str | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("OpenAI-compatible provider requires a model name")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(
                "ADCLIP_OPENAI_BASE_URL must be an absolute http(s) URL"
            )
        self.base_url = base_url.rstrip("/")
        self.model_name = model.strip()
        self.api_key = api_key
        self.timeout = timeout
        self.system_prompt = system_prompt
        self.chat_url = self._chat_endpoint(self.base_url)

    @staticmethod
    def _chat_endpoint(base_url: str) -> str:
        trimmed = base_url.rstrip("/")
        if trimmed.endswith("/chat/completions"):
            return trimmed
        if trimmed.endswith("/v1"):
            return f"{trimmed}/chat/completions"
        return f"{trimmed}/v1/chat/completions"

    @classmethod
    def from_env(
        cls,
        *,
        model: str | None,
        policy: RuntimePolicy,
    ) -> OpenAICompatibleProvider:
        base_url = (
            os.environ.get("ADCLIP_OPENAI_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
        )
        if not base_url:
            raise RuntimeError(
                "openai-compatible provider requires ADCLIP_OPENAI_BASE_URL "
                "(for example http://127.0.0.1:11434/v1)"
            )
        selected_model = (
            model
            or os.environ.get("ADCLIP_OPENAI_MODEL")
            or os.environ.get("ADCLIP_TEXT_MODEL")
        )
        if not selected_model:
            raise RuntimeError(
                "openai-compatible provider requires --model, "
                "ADCLIP_OPENAI_MODEL, or ADCLIP_TEXT_MODEL"
            )

        local = endpoint_is_loopback(base_url)
        policy.check_provider(
            "openai-compatible",
            ProviderRequirements(
                network=True,
                loopback_only=local,
                paid_api=not local,
            ),
        )
        return cls(
            base_url=base_url,
            model=selected_model,
            api_key=(
                os.environ.get("ADCLIP_OPENAI_API_KEY")
                or os.environ.get("OPENAI_API_KEY")
            ),
            timeout=float(os.environ.get("ADCLIP_OPENAI_TIMEOUT", "90")),
            system_prompt=os.environ.get("ADCLIP_TEXT_SYSTEM_PROMPT"),
        )

    async def generate(self, prompt: str, n: int) -> str:
        del n
        return await asyncio.to_thread(self._generate_sync, prompt)

    def _generate_sync(self, prompt: str) -> str:
        messages: list[dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})
        body = json.dumps(
            {
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "n": 1,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(self.chat_url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(
                f"OpenAI-compatible endpoint returned HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                f"OpenAI-compatible endpoint request failed: {exc.reason}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "OpenAI-compatible endpoint returned invalid JSON"
            ) from exc

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError(
                "OpenAI-compatible response did not contain choices[]"
            )
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            if parts:
                return "\n".join(parts)
        raise RuntimeError(
            "OpenAI-compatible response contained no textual message content"
        )
