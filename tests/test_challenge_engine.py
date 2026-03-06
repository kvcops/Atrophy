"""Tests for the ChallengeEngine and LLM providers.

Tests the challenge generation pipeline including:
- LLM response sanitisation (markdown fence stripping, key validation)
- Fallback behaviour when LLM fails
- Code sample extraction with path sanitisation
- Provider error wrapping
- Ollama SSRF prevention
"""

import json
from datetime import UTC, datetime

import pytest

from atrophy.core.challenge_engine import (
    ChallengeEngine,
    _fallback_challenge,
    _strip_markdown_fences,
    _validate_challenge,
)
from atrophy.exceptions import ProviderError
from atrophy.providers.base import BaseLLMProvider

# ── Fixtures ────────────────────────────────────────────────────────


class FakeProvider(BaseLLMProvider):
    """A fake LLM provider for testing that returns canned responses."""

    def __init__(self, responses: list[str] | None = None) -> None:
        """Initialise with a list of canned responses."""
        self._responses = responses or []
        self._call_count = 0

    async def complete(
        self, system: str, user: str, max_tokens: int = 800
    ) -> str:
        """Return the next canned response."""
        if self._call_count >= len(self._responses):
            msg = "No more canned responses."
            raise ProviderError(msg)
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp


class FailingProvider(BaseLLMProvider):
    """A provider that always raises ProviderError."""

    async def complete(
        self, system: str, user: str, max_tokens: int = 800
    ) -> str:
        """Always fail."""
        msg = "LLM is down."
        raise ProviderError(msg)


def _make_valid_challenge_json(
    skill_name: str = "testing",
    difficulty: str = "easy",
    estimated_minutes: int = 20,
) -> str:
    """Return a valid challenge JSON string."""
    return json.dumps({
        "title": "Build a Unit Test Suite",
        "description": (
            "Create a comprehensive test suite for a calculator module. "
            "Cover edge cases like division by zero and overflow. "
            "Use pytest fixtures to reduce boilerplate. "
            "Aim for 100% branch coverage."
        ),
        "skill_name": skill_name,
        "difficulty": difficulty,
        "estimated_minutes": estimated_minutes,
        "hints": [
            "Start with the happy path tests",
            "Use parametrize for edge cases",
        ],
        "success_criteria": (
            "All tests pass and coverage report shows 100% on the module."
        ),
    })


def _make_commit(
    classification: str = "human",
    diff_text: str = "+    assert result == 42\n+    pytest.mark.asyncio\n",
    files_changed: list[str] | None = None,
    ai_probability: float = 0.2,
) -> dict:
    """Return a minimal commit dict for testing."""
    return {
        "commit_hash": "a" * 40,
        "author_name": "Test Dev",
        "author_email": "test@example.com",
        "timestamp": datetime(2025, 1, 15, tzinfo=UTC),
        "message": "add tests for calculator",
        "files_changed": files_changed or ["tests/test_calc.py"],
        "additions": 10,
        "deletions": 0,
        "diff_text": diff_text,
        "minutes_since_prev": 5.0,
        "session_additions": 20,
        "ai_probability": ai_probability,
        "classification": classification,
        "velocity_score": 0.1,
        "burstiness_score": 0.3,
        "formatting_score": 0.2,
        "message_score": 0.1,
        "entropy_score": 0.2,
    }


# ── Tests: Markdown fence stripping ────────────────────────────────


class TestStripMarkdownFences:
    """Tests for _strip_markdown_fences."""

    def test_no_fences(self) -> None:
        """Plain JSON passes through unchanged."""
        raw = '{"title": "Test"}'
        assert _strip_markdown_fences(raw) == '{"title": "Test"}'

    def test_json_fence(self) -> None:
        """Strips ```json ... ``` wrapper."""
        raw = '```json\n{"title": "Test"}\n```'
        assert _strip_markdown_fences(raw) == '{"title": "Test"}'

    def test_plain_fence(self) -> None:
        """Strips ``` ... ``` without language specifier."""
        raw = '```\n{"title": "Test"}\n```'
        assert _strip_markdown_fences(raw) == '{"title": "Test"}'

    def test_whitespace_around_fences(self) -> None:
        """Handles extra whitespace around fences."""
        raw = '  ```json\n{"title": "Test"}\n```  '
        assert _strip_markdown_fences(raw) == '{"title": "Test"}'


# ── Tests: Challenge validation ─────────────────────────────────────


class TestValidateChallenge:
    """Tests for _validate_challenge."""

    def test_valid_challenge(self) -> None:
        """Valid challenge dict passes without modification."""
        data = json.loads(_make_valid_challenge_json())
        result = _validate_challenge(data)
        assert result["title"] == "Build a Unit Test Suite"
        assert result["estimated_minutes"] == 20
        assert isinstance(result["hints"], list)

    def test_missing_key_raises(self) -> None:
        """Missing required key raises KeyError."""
        data = {"title": "Test"}
        with pytest.raises(KeyError, match="Missing required key"):
            _validate_challenge(data)

    def test_wrong_type_raises(self) -> None:
        """Wrong type for a field raises TypeError."""
        data = json.loads(_make_valid_challenge_json())
        data["title"] = 12345  # should be str
        with pytest.raises(TypeError, match="expected str"):
            _validate_challenge(data)

    def test_float_minutes_coerced(self) -> None:
        """Float estimated_minutes is coerced to int."""
        data = json.loads(_make_valid_challenge_json())
        data["estimated_minutes"] = 25.5
        result = _validate_challenge(data)
        assert result["estimated_minutes"] == 25
        assert isinstance(result["estimated_minutes"], int)

    def test_minutes_clamped_low(self) -> None:
        """estimated_minutes below 5 is clamped to 5."""
        data = json.loads(_make_valid_challenge_json())
        data["estimated_minutes"] = 1
        result = _validate_challenge(data)
        assert result["estimated_minutes"] == 5

    def test_minutes_clamped_high(self) -> None:
        """estimated_minutes above 120 is clamped to 120."""
        data = json.loads(_make_valid_challenge_json())
        data["estimated_minutes"] = 999
        result = _validate_challenge(data)
        assert result["estimated_minutes"] == 120

    def test_long_string_truncated(self) -> None:
        """String fields longer than 2000 chars are truncated."""
        data = json.loads(_make_valid_challenge_json())
        data["description"] = "x" * 5000
        result = _validate_challenge(data)
        assert len(result["description"]) == 2000

    def test_invalid_difficulty_corrected(self) -> None:
        """Invalid difficulty string is corrected to 'medium'."""
        data = json.loads(_make_valid_challenge_json())
        data["difficulty"] = "nightmare"
        result = _validate_challenge(data)
        assert result["difficulty"] == "medium"


# ── Tests: Fallback challenge ───────────────────────────────────────


class TestFallbackChallenge:
    """Tests for _fallback_challenge."""

    def test_returns_valid_dict(self) -> None:
        """Fallback has all required keys."""
        result = _fallback_challenge("testing", "easy", 20)
        for key in (
            "title", "description", "skill_name", "difficulty",
            "estimated_minutes", "hints", "success_criteria",
        ):
            assert key in result

    def test_preserves_inputs(self) -> None:
        """Fallback uses the provided skill, difficulty, and minutes."""
        result = _fallback_challenge("sql_databases", "hard", 60)
        assert result["skill_name"] == "sql_databases"
        assert result["difficulty"] == "hard"
        assert result["estimated_minutes"] == 60

    def test_title_is_human_readable(self) -> None:
        """Underscored skill names are converted to title case."""
        result = _fallback_challenge("async_concurrency", "easy", 20)
        assert "Async Concurrency" in result["title"]


# ── Tests: ChallengeEngine.generate_challenges ──────────────────────


class TestGenerateChallenges:
    """Tests for ChallengeEngine.generate_challenges."""

    @pytest.mark.asyncio
    async def test_generates_three_challenges(self) -> None:
        """Generates one challenge per dead zone, up to 3."""
        responses = [
            _make_valid_challenge_json("testing", "easy", 20),
            _make_valid_challenge_json("sql_databases", "medium", 40),
            _make_valid_challenge_json("security", "hard", 60),
        ]
        provider = FakeProvider(responses)
        engine = ChallengeEngine(provider)

        result = await engine.generate_challenges(
            dead_zones=["testing", "sql_databases", "security", "extra"],
            language="python",
            code_samples={},
            top_skill="error_handling",
        )

        assert len(result) == 3
        assert result[0]["skill_name"] == "testing"
        assert result[1]["skill_name"] == "sql_databases"
        assert result[2]["skill_name"] == "security"

    @pytest.mark.asyncio
    async def test_empty_dead_zones(self) -> None:
        """Returns empty list when no dead zones provided."""
        provider = FakeProvider([])
        engine = ChallengeEngine(provider)

        result = await engine.generate_challenges(
            dead_zones=[],
            language="python",
            code_samples={},
            top_skill="testing",
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_fewer_than_three_dead_zones(self) -> None:
        """Handles fewer than 3 dead zones correctly."""
        responses = [
            _make_valid_challenge_json("testing", "easy", 20),
        ]
        provider = FakeProvider(responses)
        engine = ChallengeEngine(provider)

        result = await engine.generate_challenges(
            dead_zones=["testing"],
            language="python",
            code_samples={},
            top_skill="error_handling",
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_provider_error_returns_fallback(self) -> None:
        """When provider raises ProviderError, fallback is returned."""
        engine = ChallengeEngine(FailingProvider())

        result = await engine.generate_challenges(
            dead_zones=["testing"],
            language="python",
            code_samples={},
            top_skill="error_handling",
        )

        assert len(result) == 1
        assert result[0]["skill_name"] == "testing"
        # Should be the fallback title pattern
        assert "Testing" in result[0]["title"]

    @pytest.mark.asyncio
    async def test_malformed_json_returns_fallback(self) -> None:
        """Malformed JSON from LLM triggers fallback."""
        provider = FakeProvider(["this is not json at all {{{"])
        engine = ChallengeEngine(provider)

        result = await engine.generate_challenges(
            dead_zones=["sql_databases"],
            language="python",
            code_samples={},
            top_skill="error_handling",
        )

        assert len(result) == 1
        assert result[0]["skill_name"] == "sql_databases"

    @pytest.mark.asyncio
    async def test_strips_markdown_fences_from_response(self) -> None:
        """LLM response wrapped in markdown fences is still parsed."""
        raw_json = _make_valid_challenge_json("testing", "easy", 20)
        fenced = f"```json\n{raw_json}\n```"
        provider = FakeProvider([fenced])
        engine = ChallengeEngine(provider)

        result = await engine.generate_challenges(
            dead_zones=["testing"],
            language="python",
            code_samples={},
            top_skill="error_handling",
        )

        assert len(result) == 1
        assert result[0]["title"] == "Build a Unit Test Suite"

    @pytest.mark.asyncio
    async def test_missing_keys_returns_fallback(self) -> None:
        """LLM response missing required keys triggers fallback."""
        partial = json.dumps({"title": "Incomplete"})
        provider = FakeProvider([partial])
        engine = ChallengeEngine(provider)

        result = await engine.generate_challenges(
            dead_zones=["testing"],
            language="python",
            code_samples={},
            top_skill="error_handling",
        )

        assert len(result) == 1
        # Should be fallback, not the incomplete one
        assert result[0]["skill_name"] == "testing"
        assert "hints" in result[0]


# ── Tests: ChallengeEngine.get_code_sample ──────────────────────────


class TestGetCodeSample:
    """Tests for ChallengeEngine.get_code_sample."""

    def test_extracts_matching_lines(self) -> None:
        """Extracts added diff lines matching skill keywords."""
        commits = [_make_commit(
            diff_text=(
                "+    assert result == 42\n"
                "+    pytest.mark.asyncio\n"
                "+    print('hello')\n"
            ),
        )]
        engine = ChallengeEngine(FakeProvider())
        sample = engine.get_code_sample(commits, "testing")
        assert "assert result == 42" in sample
        assert "pytest" in sample

    def test_skips_ai_commits(self) -> None:
        """Only looks at human-classified commits."""
        commits = [_make_commit(
            classification="ai",
            diff_text="+    assert result == 42\n",
        )]
        engine = ChallengeEngine(FakeProvider())
        sample = engine.get_code_sample(commits, "testing")
        assert sample == ""

    def test_returns_empty_for_unknown_skill(self) -> None:
        """Unknown skill name returns empty string."""
        commits = [_make_commit()]
        engine = ChallengeEngine(FakeProvider())
        sample = engine.get_code_sample(commits, "nonexistent_skill")
        assert sample == ""

    def test_returns_empty_when_no_matches(self) -> None:
        """No matching keywords returns empty string."""
        commits = [_make_commit(
            diff_text="+    x = 1 + 2\n",
        )]
        engine = ChallengeEngine(FakeProvider())
        sample = engine.get_code_sample(commits, "testing")
        assert sample == ""

    def test_truncates_long_samples(self) -> None:
        """Samples exceeding max_chars are truncated."""
        long_diff = "+    assert " + "x" * 500 + "\n"
        commits = [_make_commit(diff_text=long_diff)]
        engine = ChallengeEngine(FakeProvider())
        sample = engine.get_code_sample(commits, "testing", max_chars=100)
        assert len(sample) <= 120  # max_chars + truncation marker
        assert "truncated" in sample

    def test_strips_file_paths(self) -> None:
        """Full file paths are replaced with basenames."""
        commits = [_make_commit(
            diff_text=(
                '+    assert open("/home/user/secret/test_file.py")\n'
            ),
        )]
        engine = ChallengeEngine(FakeProvider())
        sample = engine.get_code_sample(commits, "testing")
        assert "/home/user/secret" not in sample


# ── Tests: Ollama SSRF prevention ───────────────────────────────────


class TestOllamaSSRF:
    """Tests that Ollama provider rejects non-localhost URLs."""

    def test_remote_url_rejected(self) -> None:
        """Remote URLs are rejected with ProviderError."""
        from types import SimpleNamespace

        from atrophy.providers.ollama_provider import OllamaProvider

        settings = SimpleNamespace(
            ollama_mode="local",
            ollama_base_url="http://evil.com:11434",
            ollama_model="llama3.2",
        )
        with pytest.raises(ProviderError, match="localhost"):
            OllamaProvider(settings)

    def test_localhost_url_accepted(self) -> None:
        """Localhost URLs are accepted."""
        from types import SimpleNamespace

        from atrophy.providers.ollama_provider import OllamaProvider

        settings = SimpleNamespace(
            ollama_mode="local",
            ollama_base_url="http://localhost:11434",
            ollama_model="llama3.2",
        )
        # Should not raise
        provider = OllamaProvider(settings)
        assert provider._mode == "local"

    def test_loopback_url_accepted(self) -> None:
        """127.0.0.1 URLs are accepted."""
        from types import SimpleNamespace

        from atrophy.providers.ollama_provider import OllamaProvider

        settings = SimpleNamespace(
            ollama_mode="local",
            ollama_base_url="http://127.0.0.1:11434",
            ollama_model="llama3.2",
        )
        provider = OllamaProvider(settings)
        assert provider._mode == "local"

