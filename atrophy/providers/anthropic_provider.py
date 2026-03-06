"""Anthropic LLM provider for atrophy.

Implements BaseLLMProvider using the Anthropic API (claude-haiku-4-5-20251001)
for challenge generation. API key is retrieved via Settings.get_anthropic_key()
and is NEVER logged, stored, or included in error messages.
"""

import httpx
from anthropic import APIError, APITimeoutError, AsyncAnthropic

from atrophy.config import get_settings
from atrophy.exceptions import ProviderError
from atrophy.providers.base import BaseLLMProvider

# Model selection — fast, cheap Haiku variant
_MODEL = "claude-haiku-4-5-20251001"
_TIMEOUT_SECONDS = 30


class AnthropicProvider(BaseLLMProvider):
    """Anthropic LLM provider using Claude Haiku 4.5.

    Constructs the AsyncAnthropic client lazily on first ``complete()``
    call so that the API key is only unwrapped at the moment it's needed.
    """

    def __init__(self) -> None:
        """Initialise the provider (client is created lazily)."""
        self._client: AsyncAnthropic | None = None

    def _get_client(self) -> AsyncAnthropic:
        """Return (or create) the async Anthropic client.

        The API key is unwrapped from SecretStr here — the only place
        it is ever exposed as a raw string.
        """
        if self._client is None:
            settings = get_settings()
            self._client = AsyncAnthropic(
                api_key=settings.get_anthropic_key(),
                timeout=httpx.Timeout(_TIMEOUT_SECONDS),
            )
        return self._client

    async def complete(
        self, system: str, user: str, max_tokens: int = 800
    ) -> str:
        """Return completion text from Anthropic Claude Haiku.

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
            response = await client.messages.create(
                model=_MODEL,
                system=system,
                messages=[{"role": "user", "content": user}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            # Anthropic returns content blocks; first text block is the reply
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
                f"Anthropic request timed out after {_TIMEOUT_SECONDS}s. "
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
                f"Unexpected error calling Anthropic: {type(exc).__name__}"
            )
            raise ProviderError(msg) from exc
