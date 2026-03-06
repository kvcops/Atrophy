"""Base LLM provider interface for atrophy.

All provider implementations must inherit from BaseLLMProvider
and implement the complete() method.
"""

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def complete(
        self, system: str, user: str, max_tokens: int = 800
    ) -> str:
        """Return completion text from the LLM.

        Args:
            system: The system prompt.
            user: The user prompt.
            max_tokens: Maximum tokens in the response.

        Returns:
            The completion text as a string.

        Raises:
            ProviderError: If the API call fails for any reason.
        """
