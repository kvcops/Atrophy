"""OpenAI LLM provider for atrophy.

Implements BaseLLMProvider using the OpenAI API (gpt-4o-mini)
for challenge generation. API key is retrieved via Settings.get_openai_key()
and is NEVER logged, stored, or included in error messages.
"""

import httpx
from openai import APIError, APITimeoutError, AsyncOpenAI

from atrophy.config import get_settings
from atrophy.exceptions import ProviderError
from atrophy.providers.base import BaseLLMProvider

# Model selection — cheapest capable model
_MODEL = "gpt-4o-mini"
_TIMEOUT_SECONDS = 30


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM provider using gpt-4o-mini.

    Constructs the AsyncOpenAI client lazily on first ``complete()`` call
    so that the API key is only unwrapped at the moment it's needed.
    """

    def __init__(self) -> None:
        """Initialise the provider (client is created lazily)."""
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        """Return (or create) the async OpenAI client.

        The API key is unwrapped from SecretStr here — the only place
        it is ever exposed as a raw string.
        """
        if self._client is None:
            settings = get_settings()
            self._client = AsyncOpenAI(
                api_key=settings.get_openai_key(),
                timeout=httpx.Timeout(_TIMEOUT_SECONDS),
            )
        return self._client

    async def complete(
        self, system: str, user: str, max_tokens: int = 800
    ) -> str:
        """Return completion text from OpenAI gpt-4o-mini.

        Args:
            system: The system prompt.
            user: The user prompt.
            max_tokens: Maximum tokens in the response.

        Returns:
            The completion text as a string.

        Raises:
            ProviderError: If the API call fails for any reason.
        """
        client = self._get_client()
        try:
            response = await client.chat.completions.create(
                model=_MODEL,
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
            msg = f"Unexpected error calling OpenAI: {type(exc).__name__}"
            raise ProviderError(msg) from exc
