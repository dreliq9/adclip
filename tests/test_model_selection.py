import asyncio
import json

import pytest
from click.testing import CliRunner

from adclip.application import AdclipApplication
from adclip.claude_cli import ClaudeCliProvider
from adclip.cli import main
from adclip.providers.media import (
    resolve_image_provider,
    resolve_video_provider,
)
from adclip.providers.openai_compatible import OpenAICompatibleProvider
from adclip.providers.registry import default_text_registry
from adclip.runtime import RuntimeMode, RuntimePolicy


def _brief(tmp_path):
    return json.dumps({
        "product": "X",
        "value_prop": "Y",
        "audience": "Z",
        "angles": ["credibility"],
        "tone": "dry",
        "cta": "Start",
        "formats": ["google_rsa"],
        "output_dir": str(tmp_path / "campaign"),
        "variants": 1,
        "pool_size": 2,
    })


def test_registry_resolves_provider_and_model_independently():
    provider, selection = default_text_registry().resolve_with_selection(
        "claude-cli",
        model="opus",
        policy=RuntimePolicy(mode=RuntimeMode.ONLINE),
    )
    assert isinstance(provider, ClaudeCliProvider)
    assert provider._model == "opus"
    assert selection.as_dict() == {
        "provider": "claude-cli",
        "model": "opus",
    }


def test_model_selection_round_trips_through_application(tmp_path):
    app = AdclipApplication(
        runtime_policy=RuntimePolicy(mode=RuntimeMode.OFFLINE)
    )
    result = asyncio.run(
        app.generate_copy_json(
            _brief(tmp_path),
            provider_name="fake",
            model_name="fixture-model",
        )
    )
    assert result["ok"] is True
    assert result["models"]["text"] == {
        "provider": "fake",
        "model": "fixture-model",
    }


def test_openai_compatible_local_endpoint_is_allowed_offline(monkeypatch):
    monkeypatch.setenv(
        "ADCLIP_OPENAI_BASE_URL", "http://127.0.0.1:11434/v1"
    )
    provider, selection = default_text_registry().resolve_with_selection(
        "openai-compatible",
        model="qwen2.5",
        policy=RuntimePolicy(mode=RuntimeMode.OFFLINE),
    )
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model_name == "qwen2.5"
    assert selection.provider == "openai-compatible"


def test_openai_compatible_external_endpoint_is_blocked_offline(monkeypatch):
    monkeypatch.setenv("ADCLIP_OPENAI_BASE_URL", "https://models.example/v1")
    with pytest.raises(RuntimeError, match="requires network access"):
        default_text_registry().resolve(
            "openai-compatible",
            model="model-x",
            policy=RuntimePolicy(mode=RuntimeMode.OFFLINE),
        )


def test_media_provider_and_model_are_independent():
    policy = RuntimePolicy(mode=RuntimeMode.OFFLINE)
    image = resolve_image_provider("fal", model="imagen-3", policy=policy)
    video = resolve_video_provider("fal", model="veo-3.1", policy=policy)
    assert image.as_dict() == {"provider": "fal", "model": "imagen-3"}
    assert video.as_dict() == {"provider": "fal", "model": "veo-3.1"}


def test_cli_exposes_neutral_provider_and_model_flags():
    result = CliRunner().invoke(main, ["run", "--help"])
    assert result.exit_code == 0
    assert "--text-provider" in result.output
    assert "--llm" in result.output
    assert "--text-model" in result.output
    assert "--image-model" in result.output
    assert "--video-model" in result.output
