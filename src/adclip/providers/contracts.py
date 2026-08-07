"""Provider-neutral contracts and model selections used by adclip.

The legacy :mod:`adclip.llm` providers structurally implement
``TextGenerationProvider``. New providers should target this module rather
than importing a vendor SDK into application or interface code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@runtime_checkable
class TextGenerationProvider(Protocol):
    """Minimal async text-generation contract consumed by current workflows."""

    async def generate(self, prompt: str, n: int) -> str:
        """Return text containing the structured response requested by prompt."""
        ...


@dataclass(frozen=True)
class ProviderCapabilities:
    """Machine-readable capabilities exposed by a provider adapter."""

    modalities: tuple[str, ...] = ("text",)
    structured_output: bool = False
    supports_model_override: bool = True
    supports_local_inference: bool = False
    metadata: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "modalities": list(self.modalities),
            "structured_output": self.structured_output,
            "supports_model_override": self.supports_model_override,
            "supports_local_inference": self.supports_local_inference,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ModelSelection:
    """A provider/model pair selected independently of any workflow."""

    provider: str
    model: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {"provider": self.provider, "model": self.model}
