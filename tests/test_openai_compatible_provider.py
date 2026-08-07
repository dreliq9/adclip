import asyncio
import json

import pytest

from adclip.providers.openai_compatible import OpenAICompatibleProvider
from adclip.runtime import RuntimeMode, RuntimePolicy


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_request_uses_selected_model_and_standard_chat_path(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _Response({
            "choices": [{"message": {"content": '{"candidates": []}'}}]
        })

    monkeypatch.setattr(
        "adclip.providers.openai_compatible.urlopen", fake_urlopen
    )
    provider = OpenAICompatibleProvider(
        base_url="http://localhost:1234/v1",
        model="local-model",
    )
    output = asyncio.run(provider.generate("hello", 3))
    assert output == '{"candidates": []}'
    assert captured["body"]["model"] == "local-model"
    assert captured["url"].endswith("/v1/chat/completions")


def test_external_compatible_endpoint_requires_paid_api_authorization(monkeypatch):
    monkeypatch.setenv("ADCLIP_OPENAI_BASE_URL", "https://gateway.example/v1")
    with pytest.raises(RuntimeError, match="paid API charges"):
        OpenAICompatibleProvider.from_env(
            model="remote-model",
            policy=RuntimePolicy(
                mode=RuntimeMode.ONLINE,
                allow_paid_apis=False,
            ),
        )


def test_local_compatible_endpoint_needs_no_api_key(monkeypatch):
    monkeypatch.setenv("ADCLIP_OPENAI_BASE_URL", "http://localhost:8000/v1")
    monkeypatch.delenv("ADCLIP_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAICompatibleProvider.from_env(
        model="local-model",
        policy=RuntimePolicy(mode=RuntimeMode.AIR_GAPPED),
    )
    assert provider.api_key is None
