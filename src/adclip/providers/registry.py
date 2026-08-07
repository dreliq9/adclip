"""Provider registration and resolution for adclip application services."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from adclip.llm import LLMProvider
from adclip.runtime import ProviderRequirements, RuntimePolicy


LLMProviderFactory = Callable[[Any | None], LLMProvider]


@dataclass(frozen=True)
class LLMProviderSpec:
    """Metadata and a lazy factory for one text-generation provider."""

    name: str
    factory: LLMProviderFactory
    description: str = ""
    aliases: tuple[str, ...] = ()
    requirements: ProviderRequirements = field(
        default_factory=ProviderRequirements
    )


class LLMProviderRegistry:
    """Resolve named LLM providers without coupling callers to implementations."""

    def __init__(
        self,
        specs: Iterable[LLMProviderSpec] = (),
        *,
        default_name: str = "claude-cli",
    ) -> None:
        self.default_name = default_name
        self._specs: dict[str, LLMProviderSpec] = {}
        self._aliases: dict[str, str] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: LLMProviderSpec) -> None:
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
                f"Unknown LLM provider: {name!r}. Known providers: {known}"
            )
        return canonical

    def resolve(
        self,
        name: str = "default",
        *,
        session: Any | None = None,
        policy: RuntimePolicy | None = None,
    ) -> LLMProvider:
        canonical = self.canonical_name(name)
        spec = self._specs[canonical]
        active_policy = policy or RuntimePolicy.from_env()
        active_policy.check_provider(canonical, spec.requirements)
        if spec.requirements.host_session and session is None:
            raise RuntimeError(
                f"{canonical} provider requires an MCP session. Use provider="
                "'claude-cli' (the default) if no sampling-capable client "
                "is connected."
            )
        return spec.factory(session)

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
                "requirements": {
                    "network": spec.requirements.network,
                    "paid_api": spec.requirements.paid_api,
                    "host_session": spec.requirements.host_session,
                },
            }
            for spec in sorted(self._specs.values(), key=lambda item: item.name)
        ]


def _fake_factory(_session: Any | None) -> LLMProvider:
    from adclip.llm import FakeLLMProvider

    return FakeLLMProvider()


def _claude_cli_factory(_session: Any | None) -> LLMProvider:
    from adclip.claude_cli import ClaudeCliProvider

    return ClaudeCliProvider()


def _sampling_factory(session: Any | None) -> LLMProvider:
    from adclip.llm import SamplingLLMProvider

    return SamplingLLMProvider(session)


def _anthropic_factory(_session: Any | None) -> LLMProvider:
    from adclip.llm import AnthropicProvider

    return AnthropicProvider()


def default_llm_registry() -> LLMProviderRegistry:
    """Return the built-in provider registry.

    A fresh registry is returned so applications and tests can add adapters
    without mutating process-global state.
    """

    return LLMProviderRegistry(
        [
            LLMProviderSpec(
                name="fake",
                factory=_fake_factory,
                description="Deterministic in-process provider for tests.",
            ),
            LLMProviderSpec(
                name="claude-cli",
                factory=_claude_cli_factory,
                description=(
                    "Claude CLI subprocess using the user's subscription auth."
                ),
                requirements=ProviderRequirements(network=True),
            ),
            LLMProviderSpec(
                name="sampling",
                factory=_sampling_factory,
                description="Delegate generation to a sampling-capable MCP host.",
                requirements=ProviderRequirements(host_session=True),
            ),
            LLMProviderSpec(
                name="anthropic",
                factory=_anthropic_factory,
                description="Direct Anthropic API provider.",
                requirements=ProviderRequirements(network=True, paid_api=True),
            ),
        ],
        default_name="claude-cli",
    )
