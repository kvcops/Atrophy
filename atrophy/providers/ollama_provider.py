"""Ollama LLM provider for atrophy (local + cloud).

Implements BaseLLMProvider using the official ``ollama`` Python library.
Supports two modes:
  - **local**: connects to a local Ollama instance (SSRF-guarded to localhost)
  - **cloud**: connects to ollama.com's API with Bearer auth

SECURITY: In local mode, the base URL is validated to start with
``http://localhost`` or ``http://127.0.0.1`` before any request is made.
"""

from __future__ import annotations

import httpx

from atrophy.exceptions import ProviderError
from atrophy.providers.base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Ollama LLM provider supporting local and cloud modes.

    Uses the official ``ollama`` Python library's AsyncClient for all
    chat completions. In local mode the client points at localhost;
    in cloud mode it points at ``https://ollama.com`` with a Bearer
    header.
    """

    def __init__(self, settings) -> None:
        """Initialise the provider from settings.

        Args:
            settings: The Settings instance containing Ollama config.

        Raises:
            ProviderError: If the local base URL fails the SSRF check.
        """
        from ollama import AsyncClient

        self._mode = settings.ollama_mode
        self._model = (
            settings.ollama_cloud_model
            if self._mode == "cloud"
            else settings.ollama_model
        )

        if self._mode == "local":
            base = settings.ollama_base_url.rstrip("/")
            # SSRF guard — local URL must point to localhost
            if not (
                base.startswith("http://localhost")
                or base.startswith("http://127.0.0.1")
            ):
                raise ProviderError(
                    "Ollama local base URL must be "
                    "http://localhost or http://127.0.0.1"
                )
            self._client = AsyncClient(host=base)

        else:
            # Cloud: official Ollama cloud API via ollama.com
            cloud_key = settings.get_ollama_cloud_key()
            self._client = AsyncClient(
                host="https://ollama.com",
                headers={"Authorization": f"Bearer {cloud_key}"},
            )

    async def complete(
        self, system: str, user: str, max_tokens: int = 800
    ) -> str:
        """Return completion text from Ollama (local or cloud).

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
        try:
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                options={"num_predict": max_tokens},
            )
            return response["message"]["content"]

        except Exception as exc:
            err = str(exc).lower()
            if self._mode == "local" and "connection refused" in err:
                raise ProviderError(
                    "Cannot connect to Ollama. Is it running?\n"
                    "Start with: ollama serve"
                ) from exc
            if "unauthorized" in err or "401" in err:
                raise ProviderError(
                    "Ollama cloud auth failed. Check your API key at:\n"
                    "https://ollama.com/settings/keys"
                ) from exc
            raise ProviderError(
                f"Ollama {self._mode} error: {exc}"
            ) from exc

    # ── Model Discovery ──────────────────────────────────────────

    @classmethod
    async def list_local_models(
        cls, base_url: str = "http://localhost:11434"
    ) -> list[dict]:
        """List models installed on the local Ollama instance.

        ``GET {base_url}/api/tags`` — returns [] silently if Ollama
        is not running.

        Args:
            base_url: Local Ollama base URL.

        Returns:
            List of model dicts with name, size_gb, parameter_size,
            and family fields. Sorted by size ascending.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url}/api/tags")
                resp.raise_for_status()
                raw = resp.json().get("models", [])

            result: list[dict] = []
            for m in raw:
                size_gb = round(m.get("size", 0) / 1_073_741_824, 1)
                details = m.get("details", {})
                result.append({
                    "name": m["name"],
                    "size_gb": size_gb,
                    "parameter_size": details.get(
                        "parameter_size", "?"
                    ),
                    "family": details.get("family", "?"),
                })
            result.sort(key=lambda x: x["size_gb"])
            return result
        except Exception:
            return []  # Ollama not running — handled in UI

    @classmethod
    async def list_cloud_models(cls, api_key: str) -> list[dict]:
        """List models available on Ollama's cloud.

        ``GET https://ollama.com/api/tags`` with Bearer auth.

        Args:
            api_key: Ollama cloud API key from
                https://ollama.com/settings/keys.

        Returns:
            List of model dicts with name field.

        Raises:
            ProviderError: If auth fails or the request errors.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://ollama.com/api/tags",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                    },
                )
                resp.raise_for_status()
                raw = resp.json().get("models", [])

            return [{"name": m["name"]} for m in raw]

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                raise ProviderError(
                    "Invalid Ollama API key. Get one at: "
                    "https://ollama.com/settings/keys"
                ) from exc
            raise ProviderError(
                f"Ollama cloud model list error: {exc}"
            ) from exc

        except Exception as exc:
            raise ProviderError(
                f"Could not reach ollama.com: {exc}"
            ) from exc
