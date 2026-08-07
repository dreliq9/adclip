"""Text-provider registration, model selection, and lazy resolution."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from adclip.providers.contracts import (
    ModelSelection,
    ProviderCapabilities,
    TextGenerationProvider,
)
from adclip.runtime import ProviderRequirements, RuntimePolicy


@dataclass(frozen=True)
class TextProviderContext:
    """Construction context passed to a provider factory."""

    session: Any | None
    model: str | None
    policy: RuntimePolicy


TextProviderFactory = Callable[[TextProviderContext], TextGenerationProvider]


@dataclass(frozen=True)
class TextProviderSpec:
    """Metadata and a lazy factory for one text-generation provider."""

    name: str
    factory: TextProviderFactory
    description: str = ""
    aliases: tuple[str, ...] = ()
    default_model: str | None = None
    model_env: str | None = None
    model_required: bool = False
    capabilities: ProviderCapabilities = field(
        default_factory=ProviderCapabilities
    )
    requirements: ProviderRequirements = field(
        default_factory=ProviderRequirements
    )


class TextProviderRegistry:
    """Resolve provider and model independently of campaign workflows."""

    def __init__(
        self,
        specs: Iterable[TextProviderSpec] = (),
        *,
        default_name: str = "claude-cli",
    ) -> None:
        self.default_name = default_name
        self._specs: dict[str, TextProviderSpec] = {}
        self._aliases: dict[str, str] = {}
        for spec in specs:
            self.register(spec)
        self.default_name = self._aliases.get(self.default_name, self.default_name)

    def register(self, spec: TextProviderSpec) -> None:
        name = spec.name.strip()
        if not name:
            raise ValueError("Provider name must not be empty")
        if name in self._specs or name in self._aliases:
            raise ValueError(f"Provider name already registered: {name!r}")
        self._specs[name] = spec
        for alias in spec.aliases:
            alias = alias.strip()
            if not alias:
                raise ValueError(f"Empty alias on provider {name!r}")
            if alias in self._specs or alias in self._aliases:
                raise ValueError(f"Provider alias already registered: {alias!r}")
            self._aliases[alias] = name

    def canonical_name(self, name: str) -> str:
        requested = self.default_name if name == "default" else name
        canonical = self._aliases.get(requested, requested)
        if canonical not in self._specs:
            known = ", ".join(self.names(include_aliases=True))
            raise ValueError(
                f"Unknown text provider: {name!r}. Known providers: {known}"
            )
        return canonical

    def _selected_model(
        self,
        canonical: str,
        explicit_model: str | None,
    ) -> str | None:
        spec = self._specs[canonical]
        if explicit_model:
            selected = explicit_model.strip()
        else:
            derived_env = (
                "ADCLIP_"
                + canonical.upper().replace("-", "_")
                + "_MODEL"
            )
            selected = (
                os.environ.get(spec.model_env or "")
                if spec.model_env
                else None
            )
            selected = (
                selected
                or os.environ.get(derived_env)
                or os.environ.get("ADCLIP_TEXT_MODEL")
                or spec.default_model
            )
        if selected and not spec.capabilities.supports_model_override:
            if explicit_model or selected != spec.default_model:
                raise ValueError(
                    f"Provider {canonical!r} does not support model overrides"
                )
        if spec.model_required and not selected:
            raise ValueError(
                f"Provider {canonical!r} requires an explicit model. Use "
                "--model or ADCLIP_TEXT_MODEL."
            )
        return selected

    def resolve_with_selection(
        self,
        name: str = "default",
        *,
        model: str | None = None,
        session: Any | None = None,
        policy: RuntimePolicy | None = None,
    ) -> tuple[TextGenerationProvider, ModelSelection]:
        canonical = self.canonical_name(name)
        spec = self._specs[canonical]
        selected_model = self._selected_model(canonical, model)
        active_policy = policy or RuntimePolicy.from_env()
        active_policy.check_provider(canonical, spec.requirements)
        if spec.requirements.host_session and session is None:
            raise RuntimeError(
                f"{canonical} provider requires an MCP session. Select a "
                "standalone text provider when no sampling-capable host is "
                "connected."
            )
        context = TextProviderContext(
            session=session,
            model=selected_model,
            policy=active_policy,
        )
        provider = spec.factory(context)
        return provider, ModelSelection(
            provider=canonical,
            model=selected_model,
        )

    def resolve(
        self,
        name: str = "default",
        *,
        model: str | None = None,
        session: Any | None = None,
        policy: RuntimePolicy | None = None,
    ) -> TextGenerationProvider:
        provider, _selection = self.resolve_with_selection(
            name,
            model=model,
            session=session,
            policy=policy,
        )
        return provider

    def selection(
        self,
        name: str = "default",
        *,
        model: str | None = None,
    ) -> ModelSelection:
        canonical = self.canonical_name(name)
        return ModelSelection(
            provider=canonical,
            model=self._selected_model(canonical, model),
        )

    def names(self, *, include_aliases: bool = False) -> list[str]:
        names = sorted(self._specs)
        if include_aliases:
            names.extend(sorted(self._aliases))
            if "default" not in names:
                names.append("default")
        return names

    def describe(self) -> list[dict[str, object]]:
        return [
            {
                "name": spec.name,
                "aliases": list(spec.aliases),
                "description": spec.description,
                "is_default": spec.name == self.default_name,
                "default_model": spec.default_model,
                "model_required": spec.model_required,
                "capabilities": spec.capabilities.as_dict(),
                "requirements": {
                    "network": spec.requirements.network,
                    "loopback_only": spec.requirements.loopback_only,
                    "paid_api": spec.requirements.paid_api,
                    "host_session": spec.requirements.host_session,
                },
            }
            for spec in sorted(self._specs.values(), key=lambda item: item.name)
        ]

    def configured_default(self) -> dict[str, object]:
        """Describe the default without constructing a provider."""

        try:
            return self.selection("default").as_dict()
        except ValueError as exc:
            return {
                "provider": self.default_name,
                "model": None,
                "configuration_error": str(exc),
            }


def _fake_factory(context: TextProviderContext) -> TextGenerationProvider:
    del context
    from adclip.llm import FakeLLMProvider

    return FakeLLMProvider()


def _claude_cli_factory(context: TextProviderContext) -> TextGenerationProvider:
    from adclip.claude_cli import ClaudeCliProvider

    return ClaudeCliProvider(model=context.model or "sonnet")


def _sampling_factory(context: TextProviderContext) -> TextGenerationProvider:
    from adclip.llm import SamplingLLMProvider

    return SamplingLLMProvider(context.session)


def _anthropic_factory(context: TextProviderContext) -> TextGenerationProvider:
    from adclip.llm import AnthropicProvider

    return AnthropicProvider(model=context.model or "claude-sonnet-4-6")


def _openai_compatible_factory(
    context: TextProviderContext,
) -> TextGenerationProvider:
    from adclip.providers.openai_compatible import OpenAICompatibleProvider

    return OpenAICompatibleProvider.from_env(
        model=context.model,
        policy=context.policy,
    )


def default_text_registry() -> TextProviderRegistry:
    """Return the built-in, vendor-neutral text provider registry."""

    return TextProviderRegistry(
        [
            TextProviderSpec(
                name="fake",
                factory=_fake_factory,
                description="Deterministic in-process provider for tests.",
                default_model="fake-v1",
                capabilities=ProviderCapabilities(
                    structured_output=True,
                    supports_local_inference=True,
                ),
            ),
            TextProviderSpec(
                name="claude-cli",
                factory=_claude_cli_factory,
                description=(
                    "Claude CLI subprocess using the user's subscription auth."
                ),
                default_model="sonnet",
                model_env="ADCLIP_CLAUDE_MODEL",
                capabilities=ProviderCapabilities(structured_output=False),
                requirements=ProviderRequirements(network=True),
            ),
            TextProviderSpec(
                name="sampling",
                factory=_sampling_factory,
                description="Delegate generation to a sampling-capable MCP host.",
                capabilities=ProviderCapabilities(
                    structured_output=False,
                    supports_model_override=False,
                ),
                requirements=ProviderRequirements(host_session=True),
            ),
            TextProviderSpec(
                name="anthropic",
                factory=_anthropic_factory,
                description="Direct Anthropic API provider.",
                default_model="claude-sonnet-4-6",
                model_env="ADCLIP_ANTHROPIC_MODEL",
                capabilities=ProviderCapabilities(structured_output=False),
                requirements=ProviderRequirements(network=True, paid_api=True),
            ),
            TextProviderSpec(
                name="openai-compatible",
                aliases=("openai-compat", "local-http"),
                factory=_openai_compatible_factory,
                description=(
                    "Any local or hosted /v1/chat/completions-compatible endpoint."
                ),
                model_env="ADCLIP_OPENAI_MODEL",
                model_required=True,
                capabilities=ProviderCapabilities(
                    structured_output=False,
                    supports_local_inference=True,
                ),
                requirements=ProviderRequirements(
                    network=True,
                    loopback_only=True,
                ),
            ),
        ],
        default_name=os.environ.get("ADCLIP_TEXT_PROVIDER", "claude-cli"),
    )


LLMProviderRegistry = TextProviderRegistry
LLMProviderSpec = TextProviderSpec


def default_llm_registry() -> TextProviderRegistry:
    return default_text_registry()
