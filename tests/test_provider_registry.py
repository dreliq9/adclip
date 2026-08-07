import pytest

from adclip.claude_cli import ClaudeCliProvider
from adclip.llm import FakeLLMProvider
from adclip.providers import default_llm_registry
from adclip.runtime import RuntimeMode, RuntimePolicy


def test_default_registry_resolves_fake():
    provider = default_llm_registry().resolve(
        "fake",
        policy=RuntimePolicy(mode=RuntimeMode.OFFLINE),
    )
    assert isinstance(provider, FakeLLMProvider)


def test_default_alias_resolves_claude_cli():
    provider = default_llm_registry().resolve(
        "default",
        policy=RuntimePolicy(mode=RuntimeMode.ONLINE),
    )
    assert isinstance(provider, ClaudeCliProvider)


def test_offline_blocks_claude_cli_before_invocation():
    with pytest.raises(RuntimeError, match="requires network access"):
        default_llm_registry().resolve(
            "claude-cli",
            policy=RuntimePolicy(mode=RuntimeMode.OFFLINE),
        )


def test_sampling_requires_session():
    with pytest.raises(RuntimeError, match="sampling provider requires"):
        default_llm_registry().resolve(
            "sampling",
            session=None,
            policy=RuntimePolicy(mode=RuntimeMode.ONLINE),
        )


def test_registry_describes_provider_requirements():
    descriptions = {
        item["name"]: item for item in default_llm_registry().describe()
    }
    assert descriptions["anthropic"]["requirements"]["paid_api"] is True
    assert descriptions["claude-cli"]["requirements"]["network"] is True
    assert descriptions["fake"]["requirements"]["network"] is False
