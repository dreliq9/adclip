import asyncio
import json
import sys

import pytest
from click.testing import CliRunner

from adclip.application import AdclipApplication
from adclip.claude_cli import ClaudeCliProvider
from adclip.cli import main
from adclip.image_gen import resolve_model_endpoint
from adclip.providers.command import CommandTextProvider
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


def test_fake_provider_uses_selected_model_identity():
    provider, selection = default_text_registry().resolve_with_selection(
        "fake",
        model="fixture-model",
        policy=RuntimePolicy(mode=RuntimeMode.OFFLINE),
    )
    assert provider.model_name == "fixture-model"
    assert selection.model == "fixture-model"


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


def test_command_provider_runs_local_model_without_shell():
    script = (
        "import json,sys; prompt=sys.stdin.read(); "
        "print(json.dumps({'candidates':[{'headline':'Local',"
        "'body':prompt[:40],'cta':'Go'}]}))"
    )
    provider = CommandTextProvider(
        [sys.executable, "-c", script],
        model="local-fixture",
    )
    raw = asyncio.run(provider.generate("hello local model", n=1))
    assert json.loads(raw)["candidates"][0]["headline"] == "Local"


def test_command_provider_is_registered(monkeypatch):
    monkeypatch.setenv(
        "ADCLIP_COMMAND_TEXT_COMMAND",
        f'"{sys.executable}" -c "print(\"ok\")"',
    )
    provider, selection = default_text_registry().resolve_with_selection(
        "command",
        model="local-fixture",
        policy=RuntimePolicy(mode=RuntimeMode.AIR_GAPPED),
    )
    assert isinstance(provider, CommandTextProvider)
    assert selection.as_dict() == {
        "provider": "command",
        "model": "local-fixture",
    }


def test_default_provider_env_cannot_recurse_to_default(monkeypatch):
    monkeypatch.setenv("ADCLIP_TEXT_PROVIDER", "default")
    registry = default_text_registry()
    assert registry.default_name == "claude-cli"


def test_media_provider_and_model_are_independent():
    policy = RuntimePolicy(mode=RuntimeMode.OFFLINE)
    image = resolve_image_provider("fal", model="imagen-3", policy=policy)
    video = resolve_video_provider("fal", model="veo-3.1", policy=policy)
    # Resolution is side-effect free; runtime policy is checked only if the
    # paid network provider is actually invoked by a matching format.
    assert image.as_dict() == {"provider": "fal", "model": "imagen-3"}
    assert video.as_dict() == {"provider": "fal", "model": "veo-3.1"}


def test_raw_fal_image_endpoint_is_a_valid_model_id():
    assert resolve_model_endpoint("fal-ai/acme/custom-image") == (
        "fal-ai/acme/custom-image"
    )
    with pytest.raises(ValueError, match="Unknown image model alias"):
        resolve_model_endpoint("not-an-alias")


def test_cli_exposes_neutral_provider_and_model_flags():
    result = CliRunner().invoke(main, ["run", "--help"])
    assert result.exit_code == 0
    assert "--text-provider" in result.output
    assert "--llm" in result.output
    assert "--text-model" in result.output
    assert "--image-model" in result.output
    assert "--video-model" in result.output
