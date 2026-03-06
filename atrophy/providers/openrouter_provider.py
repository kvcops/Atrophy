"""OpenRouter LLM provider for atrophy.

Implements BaseLLMProvider using the OpenRouter API, which is
OpenAI-compatible and provides access to 500+ models.
API key is retrieved via Settings.get_openrouter_key()
and is NEVER logged, stored, or included in error messages.
"""

from __future__ import annotations

import httpx

from atrophy.exceptions import ProviderError
from atrophy.providers.base import BaseLLMProvider

_TIMEOUT_SECONDS = 30


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter LLM provider using any OpenRouter-hosted model.

    Uses AsyncOpenAI with base_url pointed at OpenRouter's
    OpenAI-compatible endpoint.
    """

    def __init__(self, settings) -> None:
        """Initialise the provider from settings.

        Args:
            settings: The Settings instance containing OpenRouter config.
        """
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=settings.get_openrouter_key(),
            base_url="https://openrouter.ai/api/v1",
        )
        self._model = settings.openrouter_model

    async def complete(
        self, system: str, user: str, max_tokens: int = 800
    ) -> str:
        """Return completion text from an OpenRouter-hosted model.

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
                timeout=_TIMEOUT_SECONDS,
                extra_headers={
                    "HTTP-Referer": "https://github.com/atrophy/atrophy",
                    "X-Title": "atrophy",
                },
            )
            content = response.choices[0].message.content
            if content is None:
                msg = "OpenRouter returned an empty response."
                raise ProviderError(msg)
            return content  # noqa: TRY300

        except ProviderError:
            raise

        except Exception as exc:
            msg = f"OpenRouter error: {exc}"
            raise ProviderError(msg) from exc

    # ── Model Discovery ──────────────────────────────────────────

    @classmethod
    async def fetch_models(cls, api_key: str) -> list[dict]:
        """Fetch live model list from OpenRouter's API.

        GET https://openrouter.ai/api/v1/models returns 500+ models.
        No auth is required but providing a key improves rate limits.

        Args:
            api_key: OpenRouter API key for auth header.

        Returns:
            List of model dicts with id, name, context_length,
            price_per_million, and is_free fields. Sorted with
            free models first, then alphabetically.

        Raises:
            ProviderError: If the HTTP request fails.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                raw = resp.json().get("data", [])

            models: list[dict] = []
            for m in raw:
                try:
                    prompt_price = float(
                        m.get("pricing", {}).get("prompt", "0") or "0"
                    )
                    price_per_million = round(
                        prompt_price * 1_000_000, 4
                    )
                    models.append({
                        "id": m["id"],
                        "name": m.get("name", m["id"]),
                        "context_length": m.get("context_length", 0),
                        "price_per_million": price_per_million,
                        "is_free": prompt_price == 0.0,
                    })
                except (KeyError, ValueError, TypeError):
                    continue

            # Free models first, then alphabetical
            models.sort(
                key=lambda x: (not x["is_free"], x["name"].lower())
            )
            return models

        except httpx.HTTPError as exc:
            msg = f"Could not fetch OpenRouter models: {exc}"
            raise ProviderError(msg) from exc

    @classmethod
    def search_models(
        cls, models: list[dict], query: str
    ) -> list[dict]:
        """Filter models by query string against id and name.

        Case-insensitive search. Returns up to 30 results when
        query is empty.

        Args:
            models: Full list of model dicts from fetch_models().
            query: Search string to filter by.

        Returns:
            Filtered list of matching model dicts.
        """
        if not query.strip():
            return models[:30]
        q = query.lower()
        return [
            m
            for m in models
            if q in m["id"].lower() or q in m["name"].lower()
        ]
