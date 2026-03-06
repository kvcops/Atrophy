"""LLM-based skill classifier for unknown languages / complex diffs.

Uses an LLM provider to classify code diffs into skill categories
when tree-sitter analysis is unavailable. Results are cached by
diff hash to avoid redundant API calls.

Security:
    - Diff text is truncated to 800 chars before sending.
    - All LLM responses are validated and sanitised.
    - Errors return empty dict — never crash skill mapping.
    - No pickle or shelve — cache is in-memory dict only.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re

from atrophy.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# ── Valid skill names for validation ────────────────────────────────

VALID_SKILLS: frozenset[str] = frozenset({
    "async_concurrency",
    "data_structures",
    "sql_databases",
    "regex_parsing",
    "error_handling",
    "api_design",
    "testing",
    "algorithms",
    "system_io",
    "security",
})

# ── LLM prompts ────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a code analysis tool. Analyze the given code diff and identify
which software engineering skill categories it demonstrates.

The 10 skill categories are:
async_concurrency, data_structures, sql_databases, regex_parsing,
error_handling, api_design, testing, algorithms, system_io, security

Respond ONLY with a JSON object mapping skill names to confidence \
scores (0.0-1.0).
Only include skills with score > 0.3. Example:
{"error_handling": 0.9, "async_concurrency": 0.6}\
"""


class LLMSkillClassifier:
    """Classifies code diffs into skill categories using an LLM.

    Uses the configured LLM provider to analyze diffs that can't be
    parsed by tree-sitter (unsupported languages, complex context).
    Results are cached in-memory by diff hash.
    """

    def __init__(self, provider: BaseLLMProvider) -> None:
        """Initialize with an LLM provider.

        Args:
            provider: Any concrete ``BaseLLMProvider`` implementation.
        """
        self._provider = provider
        self._cache: dict[str, dict[str, float]] = {}

    async def classify_diff(
        self, diff_text: str, language: str,
    ) -> dict[str, float]:
        """Classify a diff into skill categories via LLM.

        Args:
            diff_text: Raw diff text (added lines preferred).
            language: Programming language name.

        Returns:
            Dict mapping skill names to confidence scores (0.0-1.0).
            Empty dict on error or short diffs.
        """
        # Skip very short diffs — not worth an API call
        if len(diff_text) < 50:
            return {}

        # Check cache first
        cache_key = hashlib.sha256(
            diff_text.encode("utf-8", errors="replace")
        ).hexdigest()[:16]

        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # Truncate diff to 800 chars to save tokens
            truncated = diff_text[:800]
            user_prompt = (
                f"Language: {language}\n\n"
                f"Code diff (added lines only):\n{truncated}"
            )

            raw = await self._provider.complete(
                system=_SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=200,
            )

            result = self._parse_response(raw)
            self._cache[cache_key] = result
            return result

        except Exception:
            logger.debug(
                "LLM skill classification failed",
                exc_info=True,
            )
            return {}

    @staticmethod
    def _parse_response(raw: str) -> dict[str, float]:
        """Parse and validate the LLM response.

        Security:
            - Strips markdown fences before parsing.
            - Validates all keys are valid skill names.
            - Clamps all values to 0.0-1.0.
            - Truncates string fields > 2000 chars (never used here).

        Args:
            raw: Raw LLM response text.

        Returns:
            Validated dict of skill → confidence. Empty on failure.
        """
        # Strip markdown fences
        text = raw.strip()
        text = re.sub(r"^```\w*\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {}

        if not isinstance(parsed, dict):
            return {}

        result: dict[str, float] = {}
        for key, value in parsed.items():
            # Validate key
            if key not in VALID_SKILLS:
                continue

            # Validate and clamp value
            try:
                score = float(value)
            except (TypeError, ValueError):
                continue

            score = max(0.0, min(1.0, score))
            if score > 0.3:
                result[key] = round(score, 2)

        return result
