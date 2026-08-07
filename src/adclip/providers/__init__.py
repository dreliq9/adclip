"""Provider contracts, adapters, and registries for standalone adclip."""

from adclip.providers.contracts import (
    ModelSelection,
    ProviderCapabilities,
    TextGenerationProvider,
)
from adclip.providers.registry import (
    LLMProviderRegistry,
    LLMProviderSpec,
    TextProviderRegistry,
    TextProviderSpec,
    default_llm_registry,
    default_text_registry,
)

__all__ = [
    "ModelSelection",
    "ProviderCapabilities",
    "TextGenerationProvider",
    "TextProviderRegistry",
    "TextProviderSpec",
    "default_text_registry",
    "LLMProviderRegistry",
    "LLMProviderSpec",
    "default_llm_registry",
]
