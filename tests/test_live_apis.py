"""Guardrail: live third-party APIs must be explicitly opted into."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clear_gate(monkeypatch):
    monkeypatch.delenv("ADCLIP_ALLOW_LIVE_APIS", raising=False)


def test_allow_live_apis_unset_defaults_false():
    from adclip._live_apis import allow_live_apis

    assert allow_live_apis() is False


@pytest.mark.parametrize("value", ["1", "true", "YES", "on", "True"])
def test_allow_live_apis_truthy(monkeypatch, value):
    from adclip._live_apis import allow_live_apis

    monkeypatch.setenv("ADCLIP_ALLOW_LIVE_APIS", value)
    assert allow_live_apis() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "", "maybe"])
def test_allow_live_apis_falsy(monkeypatch, value):
    from adclip._live_apis import allow_live_apis

    monkeypatch.setenv("ADCLIP_ALLOW_LIVE_APIS", value)
    assert allow_live_apis() is False


def test_require_live_apis_raises_without_gate():
    from adclip._live_apis import require_live_apis

    with pytest.raises(RuntimeError, match="ADCLIP_ALLOW_LIVE_APIS"):
        require_live_apis("test provider")


def test_anthropic_provider_blocked_without_gate(monkeypatch):
    """Even with a key in env, AnthropicProvider refuses unless opted in."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake-test-key")

    from adclip.llm import AnthropicProvider

    with pytest.raises(RuntimeError, match="ADCLIP_ALLOW_LIVE_APIS"):
        AnthropicProvider()


def test_fal_image_gen_blocked_without_gate(monkeypatch):
    """Even with FAL_KEY in env, _check_key refuses unless opted in."""
    monkeypatch.setenv("FAL_KEY", "fal-fake-test-key")

    from adclip.image_gen import _check_key

    with pytest.raises(RuntimeError, match="ADCLIP_ALLOW_LIVE_APIS"):
        _check_key()


def test_fal_video_gen_blocked_without_gate(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "fal-fake-test-key")

    from adclip.video_gen import _check_key

    with pytest.raises(RuntimeError, match="ADCLIP_ALLOW_LIVE_APIS"):
        _check_key()


def test_fal_image_gen_still_needs_key_when_gate_open(monkeypatch):
    """With gate open but no FAL_KEY, you get the clear key-missing error."""
    monkeypatch.setenv("ADCLIP_ALLOW_LIVE_APIS", "1")
    monkeypatch.delenv("FAL_KEY", raising=False)

    from adclip.image_gen import _check_key

    with pytest.raises(RuntimeError, match="FAL_KEY not set"):
        _check_key()
