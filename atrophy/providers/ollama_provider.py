"""Ollama (local) LLM provider for atrophy.

Implements BaseLLMProvider using a local Ollama instance for
challenge generation. URL is validated to localhost only (SSRF prevention).
Uses httpx.AsyncClient to POST to the Ollama /api/generate endpoint and
parses the streaming NDJSON response.
"""

import json

import httpx

from atrophy.config import get_settings
from atrophy.exceptions import ProviderError
from atrophy.providers.base import BaseLLMProvider

_TIMEOUT_SECONDS = 60  # Local models are slower


class OllamaProvider(BaseLLMProvider):
    """Ollama LLM provider using a local model.

    SECURITY: The base URL is validated to start with ``http://localhost``
    or ``http://127.0.0.1`` before any request is made, preventing SSRF
    attacks from misconfigured URLs pointing to remote servers.
    """

    def __init__(self) -> None:
        """Initialise the provider (URL and model read from settings)."""
        settings = get_settings()
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_model
        self._validate_url()

    def _validate_url(self) -> None:
        """SSRF guard — ensure Ollama URL points to localhost only.

        Raises:
            ProviderError: If the URL does not start with a localhost
                prefix.
        """
        allowed_prefixes = ("http://localhost", "http://127.0.0.1")
        if not self._base_url.startswith(allowed_prefixes):
            msg = (
                "Ollama base URL must start with http://localhost or "
                "http://127.0.0.1 (SSRF prevention). "
                f"Got: {self._base_url}"
            )
            raise ProviderError(msg)

    async def complete(
        self, system: str, user: str, max_tokens: int = 800
    ) -> str:
        """Return completion text from local Ollama instance.

        Sends a POST to ``/api/generate`` with ``stream: false`` for
        simplicity, but also handles streaming NDJSON responses from
        older Ollama versions.

        Args:
            system: The system prompt.
            user: The user prompt.
            max_tokens: Maximum tokens in the response (passed as
                ``num_predict``).

        Returns:
            The completion text as a string.

        Raises:
            ProviderError: If the API call fails for any reason.
        """
        # Re-validate URL every call as an extra safety measure
        self._validate_url()

        url = f"{self._base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self._model,
            "system": system,
            "prompt": user,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            },
        }

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(_TIMEOUT_SECONDS)
            ) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return self._parse_response(response.text)

        except httpx.TimeoutException as exc:
            msg = (
                f"Ollama request timed out after {_TIMEOUT_SECONDS}s. "
                f"Is Ollama running at {self._base_url}?"
            )
            raise ProviderError(msg) from exc

        except httpx.HTTPStatusError as exc:
            msg = (
                f"Ollama returned HTTP {exc.response.status_code}. "
                f"Is the model '{self._model}' pulled? "
                f"Try: ollama pull {self._model}"
            )
            raise ProviderError(msg) from exc

        except httpx.ConnectError as exc:
            msg = (
                f"Cannot connect to Ollama at {self._base_url}. "
                "Is Ollama running? Start it with: ollama serve"
            )
            raise ProviderError(msg) from exc

        except ProviderError:
            raise

        except Exception as exc:
            msg = f"Unexpected error calling Ollama: {type(exc).__name__}"
            raise ProviderError(msg) from exc

    @staticmethod
    def _parse_response(raw: str) -> str:
        """Parse Ollama response, handling both single JSON and NDJSON.

        Ollama may return either:
        - A single JSON object with a ``response`` key (stream=false)
        - Multiple newline-delimited JSON objects (streaming mode)

        Args:
            raw: The raw response body text.

        Returns:
            The concatenated completion text.

        Raises:
            ProviderError: If the response cannot be parsed.
        """
        lines = raw.strip().splitlines()

        # Single JSON response (stream=false)
        if len(lines) == 1:
            try:
                data = json.loads(lines[0])
                text = data.get("response", "")
                if not text:
                    msg = "Ollama returned an empty response."
                    raise ProviderError(msg)
                return text  # noqa: TRY300
            except json.JSONDecodeError as exc:
                msg = "Failed to parse Ollama response as JSON."
                raise ProviderError(msg) from exc

        # NDJSON streaming response — concatenate all response fragments
        fragments: list[str] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                fragment = data.get("response", "")
                if fragment:
                    fragments.append(fragment)
            except json.JSONDecodeError:
                # Skip malformed lines in the stream
                continue

        if not fragments:
            msg = "Ollama returned no content in the streamed response."
            raise ProviderError(msg)

        return "".join(fragments)
