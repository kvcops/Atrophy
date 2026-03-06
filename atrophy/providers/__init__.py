"""atrophy LLM providers package.

Exports the provider factory ``get_provider()`` which returns the
appropriate BaseLLMProvider based on the current Settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from atrophy.exceptions import ProviderError
from atrophy.providers.base import BaseLLMProvider

if TYPE_CHECKING:
    from atrophy.config import Settings

__all__ = ["BaseLLMProvider", "ProviderError", "get_provider"]


def get_provider(settings: Settings) -> BaseLLMProvider:
    """Return the configured LLM provider instance.

    Lazy-imports each provider so their heavy dependencies (openai,
    anthropic, ollama) are only loaded when actually needed.

    Args:
        settings: The application Settings instance.

    Returns:
        A BaseLLMProvider implementation ready for use.

    Raises:
        ProviderError: If no provider is configured or the provider
            type is unknown.
    """
    provider = settings.llm_provider

    if provider == "openai":
        from atrophy.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(settings)

    elif provider == "anthropic":
        from atrophy.providers.anthropic_provider import (
            AnthropicProvider,
        )

        return AnthropicProvider(settings)

    elif provider == "openrouter":
        from atrophy.providers.openrouter_provider import (
            OpenRouterProvider,
        )

        return OpenRouterProvider(settings)

    elif provider == "ollama":
        from atrophy.providers.ollama_provider import OllamaProvider

        return OllamaProvider(settings)

    else:
        raise ProviderError(
            "No LLM provider configured. Run: atrophy config"
        )
