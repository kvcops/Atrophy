"""OpenAI LLM provider for atrophy.

Implements BaseLLMProvider using the OpenAI API for challenge
generation. API key is retrieved via Settings.get_openai_key()
and is NEVER logged, stored, or included in error messages.
"""

from __future__ import annotations

import httpx
from openai import APIError, APITimeoutError, AsyncOpenAI

from atrophy.exceptions import ProviderError
from atrophy.providers.base import BaseLLMProvider

_TIMEOUT_SECONDS = 30


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider.

    Constructs the AsyncOpenAI client eagerly from settings so the
    API key is unwrapped exactly once at construction time.
    """

    def __init__(self, settings) -> None:
        """Initialise the provider from settings.

        Args:
            settings: The Settings instance containing OpenAI config.
        """
        self._model = settings.openai_model
        self._client = AsyncOpenAI(
            api_key=settings.get_openai_key(),
            timeout=httpx.Timeout(_TIMEOUT_SECONDS),
        )

    async def complete(
        self, system: str, user: str, max_tokens: int = 800
    ) -> str:
        """Return completion text from OpenAI.

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
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            content = response.choices[0].message.content
            if content is None:
                msg = "OpenAI returned an empty response."
                raise ProviderError(msg)
            return content  # noqa: TRY300

        except APITimeoutError as exc:
            msg = (
                f"OpenAI request timed out after {_TIMEOUT_SECONDS}s. "
                "Check your network connection and try again."
            )
            raise ProviderError(msg) from exc

        except APIError as exc:
            msg = (
                f"OpenAI API error (status {exc.status_code}): "
                f"{exc.message}"
            )
            raise ProviderError(msg) from exc

        except ProviderError:
            raise

        except Exception as exc:
            msg = (
                f"Unexpected error calling OpenAI: "
                f"{type(exc).__name__}"
            )
            raise ProviderError(msg) from exc
