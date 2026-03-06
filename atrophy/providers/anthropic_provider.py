"""Anthropic LLM provider for atrophy.

Implements BaseLLMProvider using the Anthropic API for challenge
generation. API key is retrieved via Settings.get_anthropic_key()
and is NEVER logged, stored, or included in error messages.
"""

from __future__ import annotations

import httpx
from anthropic import APIError, APITimeoutError, AsyncAnthropic

from atrophy.exceptions import ProviderError
from atrophy.providers.base import BaseLLMProvider

_TIMEOUT_SECONDS = 30


class AnthropicProvider(BaseLLMProvider):
    """Anthropic LLM provider.

    Constructs the AsyncAnthropic client eagerly from settings so
    the API key is unwrapped exactly once at construction time.
    """

    def __init__(self, settings) -> None:
        """Initialise the provider from settings.

        Args:
            settings: The Settings instance containing Anthropic config.
        """
        self._model = settings.anthropic_model
        self._client = AsyncAnthropic(
            api_key=settings.get_anthropic_key(),
            timeout=httpx.Timeout(_TIMEOUT_SECONDS),
        )

    async def complete(
        self, system: str, user: str, max_tokens: int = 800
    ) -> str:
        """Return completion text from Anthropic Claude.

        Args:
            system: The system prompt.
            user: The user prompt.
            max_tokens: Maximum tokens in the response.

        Returns:
            The completion text as a string.

        Raises:
            ProviderError: If the API call fails for any reason.
        """
        try:
            response = await self._client.messages.create(
                model=self._model,
                system=system,
                messages=[{"role": "user", "content": user}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            # Anthropic returns content blocks; first text block is
            # the reply.
            if not response.content:
                msg = "Anthropic returned an empty response."
                raise ProviderError(msg)

            text = response.content[0].text
            if not text:
                msg = "Anthropic returned an empty text block."
                raise ProviderError(msg)
            return text  # noqa: TRY300

        except APITimeoutError as exc:
            msg = (
                "Anthropic request timed out after "
                f"{_TIMEOUT_SECONDS}s. "
                "Check your network connection and try again."
            )
            raise ProviderError(msg) from exc

        except APIError as exc:
            msg = (
                f"Anthropic API error (status {exc.status_code}): "
                f"{exc.message}"
            )
            raise ProviderError(msg) from exc

        except ProviderError:
            raise

        except Exception as exc:
            msg = (
                "Unexpected error calling Anthropic: "
                f"{type(exc).__name__}"
            )
            raise ProviderError(msg) from exc
