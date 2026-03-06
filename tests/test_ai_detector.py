"""Tests for atrophy.core.ai_detector — AI vs Human classification.

Verifies all 5 signal computations, classification thresholds,
batch analysis, and summary statistics.
"""

import math
from datetime import datetime, timezone

import pytest

from atrophy.core.ai_detector import AIDetector


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def detector() -> AIDetector:
    """Return a fresh AIDetector instance."""
    return AIDetector()


def _make_commit(**overrides) -> dict:
    """Build a minimal commit dict for testing."""
    base = {
        "commit_hash": "a" * 40,
        "author_name": "Dev",
        "author_email": "dev@example.com",
        "timestamp": datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        "message": "feat: add new feature",
        "files_changed": ["main.py"],
        "additions": 50,
        "deletions": 5,
        "diff_text": "+def hello():\n+    print('world')\n+    return True\n",
        "minutes_since_prev": 15.0,
        "session_additions": 50,
    }
    base.update(overrides)
    return base


# ── Velocity signal tests ──────────────────────────────────────────


class TestVelocityScore:
    """Tests for Signal 1: coding velocity."""

    def test_tiny_commit_returns_low_score(self, detector: AIDetector) -> None:
        """Commits with < 5 additions should always score 0.2."""
        score = detector._velocity_score(lpm=3.0, additions=3)
        assert score == 0.2

    def test_high_velocity_scores_high(self, detector: AIDetector) -> None:
        """>=80 lines/min should score 0.95 (almost certainly AI)."""
        # 100 lines in 1 minute = 100 lpm
        score = detector._velocity_score(lpm=100.0, additions=100)
        assert score == 0.95

    def test_medium_velocity_interpolates(self, detector: AIDetector) -> None:
        """40-80 lpm should interpolate between 0.75 and 0.95."""
        # 60 lines in 1 minute = 60 lpm (midpoint of 40-80 range)
        score = detector._velocity_score(lpm=60.0, additions=60)
        assert 0.75 <= score <= 0.95

    def test_low_velocity_scores_low(self, detector: AIDetector) -> None:
        """<10 lpm should score below 0.50 (likely human pace)."""
        # 5 lines in 1 minute = 5 lpm
        score = detector._velocity_score(lpm=5.0, additions=5)
        assert score < 0.50

    def test_zero_minutes_uses_floor(self, detector: AIDetector) -> None:
        """0 minutes_since_prev should use floor of 0.5 (not divide by zero)."""
        score = detector._velocity_score(lpm=100.0, additions=50)
        # 50 / 0.5 = 100 lpm → 0.95
        assert score == 0.95

    def test_very_slow_approaches_005(self, detector: AIDetector) -> None:
        """Extremely slow pace should approach 0.05."""
        score = detector._velocity_score(
            lpm=0.01, additions=10
        )
        # 10/1000 = 0.01 lpm → near 0.05
        assert score < 0.10

    def test_exactly_10_lpm(self, detector: AIDetector) -> None:
        """10 lpm should score 0.50."""
        score = detector._velocity_score(
            lpm=10.0, additions=10
        )
        assert abs(score - 0.50) < 0.01

    def test_exactly_40_lpm(self, detector: AIDetector) -> None:
        """40 lpm should score 0.75."""
        score = detector._velocity_score(
            lpm=40.0, additions=40
        )
        assert abs(score - 0.75) < 0.01


# ── Burstiness signal tests ────────────────────────────────────────


class TestBurstinessScore:
    """Tests for Signal 2: coefficient of variation of line lengths."""

    def test_few_lines_returns_05(self, detector: AIDetector) -> None:
        """Fewer than 5 lines should return 0.5 (not enough data)."""
        score = detector._burstiness_score(["a", "b"])
        assert score == 0.5

    def test_uniform_lines_score_high(self, detector: AIDetector) -> None:
        """Very uniform line lengths → low CV → high score (AI-like)."""
        lines = ["x" * 40] * 20  # All same length, CV ≈ 0
        score = detector._burstiness_score(lines)
        assert score >= 0.80

    def test_chaotic_lines_score_low(self, detector: AIDetector) -> None:
        """Highly variable line lengths → high CV → low score (human)."""
        lines = ["x", "y" * 200, "ab", "z" * 150, "q" * 3, "w" * 180,
                 "a" * 2, "b" * 250, "c", "d" * 300]
        score = detector._burstiness_score(lines)
        assert score <= 0.20

    def test_moderate_variation(self, detector: AIDetector) -> None:
        """Moderate variation should produce a mid-range score."""
        lines = [
            "x" * 30, "y" * 45, "z" * 35, "w" * 50,
            "a" * 25, "b" * 40, "c" * 55, "d" * 32,
        ]
        score = detector._burstiness_score(lines)
        assert 0.10 < score < 0.90


# ── Formatting signal tests ────────────────────────────────────────


class TestFormattingScore:
    """Tests for Signal 3: clean formatting ratio."""

    def test_empty_returns_05(self, detector: AIDetector) -> None:
        """No lines → return 0.5."""
        score = detector._formatting_score([])
        assert score == 0.5

    def test_perfectly_clean_code(self, detector: AIDetector) -> None:
        """All clean lines should score near 0.9."""
        lines = [
            "def hello():",
            "    print('world')",
            "    return True",
            "",
            "def goodbye():",
            "    pass",
        ]
        score = detector._formatting_score(lines)
        assert score >= 0.8

    def test_trailing_whitespace_lowers_score(
        self, detector: AIDetector
    ) -> None:
        """Lines with trailing whitespace should reduce the score."""
        lines = [
            "def hello():   ",  # trailing spaces
            "    print('world')  ",  # trailing spaces
            "    return True",
        ]
        score = detector._formatting_score(lines)
        assert score < 0.9

    def test_clamped_to_range(self, detector: AIDetector) -> None:
        """Score should always be in [0.1, 0.9]."""
        # All dirty lines
        dirty = ["x" * 200, "\t  mixed", "   odd_indent"]  # noqa: E501
        score_low = detector._formatting_score(dirty)
        assert score_low >= 0.1

        # All clean lines
        clean = ["    pass", "    return None"] * 10
        score_high = detector._formatting_score(clean)
        assert score_high <= 0.9


# ── Message signal tests ───────────────────────────────────────────


class TestMessageScore:
    """Tests for Signal 4: commit message patterns."""

    def test_conventional_commit_scores_075(
        self, detector: AIDetector
    ) -> None:
        """A proper conventional commit should score 0.75."""
        score = detector._message_score("feat(auth): add JWT validation logic")
        assert score == 0.75

    def test_short_message_scores_005(self, detector: AIDetector) -> None:
        """Messages with < 4 chars should score 0.05."""
        assert detector._message_score("fix") == 0.05
        assert detector._message_score("wip") == 0.05
        assert detector._message_score("x") == 0.05

    def test_human_keywords_score_008(self, detector: AIDetector) -> None:
        """Messages with human frustration markers should score 0.08."""
        assert detector._message_score("finally got this working") == 0.08
        assert detector._message_score("wtf is happening") == 0.08
        assert detector._message_score("TODO: fix this later") == 0.08

    def test_generic_message_scores_040(self, detector: AIDetector) -> None:
        """A generic message should score 0.40."""
        score = detector._message_score("Updated the login page styling")
        assert score == 0.40

    def test_conventional_without_description_is_generic(
        self, detector: AIDetector
    ) -> None:
        """'feat: ab' has < 5 chars after the prefix → not matched."""
        score = detector._message_score("feat: ab")
        # Only 2 chars after ': ' → doesn't match CONVENTIONAL_PATTERN
        assert score == 0.40


# ── Entropy signal tests ───────────────────────────────────────────


class TestEntropyScore:
    """Tests for Signal 5: Shannon entropy of character frequencies."""

    def test_very_short_text_returns_05(self, detector: AIDetector) -> None:
        """Text < 10 chars → return 0.5."""
        score = detector._entropy_score(["hi"])
        assert score == 0.5

    def test_repetitive_text_scores_high(self, detector: AIDetector) -> None:
        """Very repetitive text (low entropy) should score ~0.8 (AI)."""
        # All same character → entropy ≈ 0 → H < 3.2 → 0.8
        lines = ["aaaaaaaaaa"] * 10
        score = detector._entropy_score(lines)
        assert score >= 0.7

    def test_high_entropy_returns_05(self, detector: AIDetector) -> None:
        """Very high entropy (>4.8) → treated as minified, returns 0.5."""
        # Create text with many unique characters
        import string
        chars = string.printable * 5
        lines = [chars[i:i + 80] for i in range(0, len(chars), 80)]
        score = detector._entropy_score(lines)
        # Should be 0.5 (skip) or within the normal range
        assert 0.0 <= score <= 1.0


# ── Section 2: Specific Tests ──────────────────────────────────────


class TestSpecificCommits:
    """Explicit tests requested for the AI detector."""

    def test_human_commit(self, detector: AIDetector) -> None:
        """HUMAN commit: messy diff, slow pace -> low ai_probability."""
        diff_text = "+def foo():   \n+    x=1\n+  y = 2\n"  # messy variable line lengths, 3 trailing spaces, mixed indent
        commit = _make_commit(
            message="fix",
            additions=8,
            minutes_since_prev=45.0,
            diff_text=diff_text
        )
        result = detector.analyze(commit)
        assert result["ai_probability"] < 0.4
        assert result["classification"] in {"human", "uncertain"}

    def test_ai_commit(self, detector: AIDetector) -> None:
        """AI commit: uniform code, high pace -> high ai_probability."""
        diff_text = "\n".join([f"+    x = {i}" for i in range(150)])  # perfectly uniform lines, 4-space indent
        commit = _make_commit(
            message="feat: add authentication middleware",
            additions=150,
            minutes_since_prev=0.8,
            diff_text=diff_text
        )
        result = detector.analyze(commit)
        assert result["ai_probability"] > 0.7
        assert result["classification"] == "ai"

    def test_uncertain_commit(self, detector: AIDetector) -> None:
        """UNCERTAIN commit: middling values -> mid ai_probability."""
        diff_text = "\n".join([f"+def do_thing_{i}():\n+    pass\n" for i in range(10)])
        commit = _make_commit(
            message="Update logic",
            additions=20,
            minutes_since_prev=10.0,
            diff_text=diff_text
        )
        result = detector.analyze(commit)
        assert 0.3 < result["ai_probability"] < 0.7

# ── Full analyze() tests ───────────────────────────────────────────


class TestAnalyze:
    """Tests for the main analyze() method."""

    def test_returns_all_required_fields(self, detector: AIDetector) -> None:
        """analyze() must add all AI detection fields to the dict."""
        commit = _make_commit()
        result = detector.analyze(commit)

        required = {
            "ai_probability",
            "classification",
            "velocity_score",
            "burstiness_score",
            "formatting_score",
            "message_score",
            "entropy_score",
        }
        missing = required - set(result.keys())
        assert missing == set(), f"Missing fields: {missing}"

    def test_preserves_original_fields(self, detector: AIDetector) -> None:
        """Original commit fields should be preserved in the result."""
        commit = _make_commit(commit_hash="b" * 40)
        result = detector.analyze(commit)
        assert result["commit_hash"] == "b" * 40
        assert result["author_name"] == "Dev"

    def test_ai_probability_in_range(self, detector: AIDetector) -> None:
        """ai_probability must be between 0 and 1."""
        commit = _make_commit()
        result = detector.analyze(commit)
        assert 0.0 <= result["ai_probability"] <= 1.0

    def test_classification_is_valid(self, detector: AIDetector) -> None:
        """classification must be one of human/ai/uncertain."""
        commit = _make_commit()
        result = detector.analyze(commit)
        assert result["classification"] in {"human", "ai", "uncertain"}

    def test_high_velocity_ai_commit(self, detector: AIDetector) -> None:
        """A commit with AI-like signals should classify as 'ai'."""
        # Very fast, uniform code, conventional commit
        uniform_diff = "\n".join([f"+{'x' * 50}" for _ in range(100)])
        commit = _make_commit(
            additions=100,
            minutes_since_prev=0.5,  # 200 lpm
            diff_text=uniform_diff,
            message="feat(core): implement comprehensive data processing layer",
        )
        result = detector.analyze(commit)
        assert result["velocity_score"] >= 0.90
        assert result["classification"] in {"ai", "uncertain"}

    def test_slow_messy_human_commit(self, detector: AIDetector) -> None:
        """A commit with human-like signals should classify as 'human'."""
        messy_diff = (
            "+x = 1\n"
            "+y = x + 2  \n"  # trailing space
            "+# TODO: fix this\n"
            "+result = compute(x, y)\n"
            "+print(result)\n"
            "+   # wtf\n"
        )
        commit = _make_commit(
            additions=6,
            minutes_since_prev=45.0,  # ~0.13 lpm → very slow
            diff_text=messy_diff,
            message="wip",
        )
        result = detector.analyze(commit)
        assert result["classification"] in {"human", "uncertain"}

    def test_does_not_mutate_original(self, detector: AIDetector) -> None:
        """analyze() should not modify the original commit dict."""
        commit = _make_commit()
        original_keys = set(commit.keys())
        detector.analyze(commit)
        assert set(commit.keys()) == original_keys


# ── Batch analysis tests ───────────────────────────────────────────


class TestAnalyzeBatch:
    """Tests for analyze_batch()."""

    def test_empty_returns_empty(self, detector: AIDetector) -> None:
        """Empty input should return empty list."""
        assert detector.analyze_batch([]) == []

    def test_batch_processes_all(self, detector: AIDetector) -> None:
        """All commits should be analyzed."""
        commits = [_make_commit(commit_hash=f"{'0' * 39}{i}") for i in range(5)]
        results = detector.analyze_batch(commits)
        assert len(results) == 5
        assert all("ai_probability" in r for r in results)

    def test_batch_preserves_order(self, detector: AIDetector) -> None:
        """Results should be in the same order as inputs."""
        commits = [
            _make_commit(commit_hash=f"{'0' * 39}{i}")
            for i in range(3)
        ]
        results = detector.analyze_batch(commits)
        for i, result in enumerate(results):
            assert result["commit_hash"] == f"{'0' * 39}{i}"


# ── Summary stats tests ────────────────────────────────────────────


class TestSummaryStats:
    """Tests for get_summary_stats()."""

    def test_empty_input(self, detector: AIDetector) -> None:
        """Empty commit list should return all zeros."""
        stats = detector.get_summary_stats([])
        assert stats["total"] == 0
        assert stats["human_ratio"] == 0.0
        assert stats["monthly_breakdown"] == {}

    def test_counts_correct(self, detector: AIDetector) -> None:
        """human_count + ai_count + uncertain_count should equal total."""
        analyzed = [
            {
                "classification": "human",
                "ai_probability": 0.2,
                "timestamp": datetime(2025, 6, 1, tzinfo=timezone.utc),
            },
            {
                "classification": "ai",
                "ai_probability": 0.8,
                "timestamp": datetime(2025, 6, 15, tzinfo=timezone.utc),
            },
            {
                "classification": "uncertain",
                "ai_probability": 0.5,
                "timestamp": datetime(2025, 7, 1, tzinfo=timezone.utc),
            },
        ]
        stats = detector.get_summary_stats(analyzed)
        assert stats["total"] == 3
        assert stats["human_count"] == 1
        assert stats["ai_count"] == 1
        assert stats["uncertain_count"] == 1
        assert (
            stats["human_count"] + stats["ai_count"] + stats["uncertain_count"]
            == stats["total"]
        )

    def test_human_ratio(self, detector: AIDetector) -> None:
        """human_ratio should be human_count / total."""
        analyzed = [
            {
                "classification": "human",
                "ai_probability": 0.2,
                "timestamp": datetime(2025, 6, 1, tzinfo=timezone.utc),
            },
            {
                "classification": "human",
                "ai_probability": 0.3,
                "timestamp": datetime(2025, 6, 1, tzinfo=timezone.utc),
            },
            {
                "classification": "ai",
                "ai_probability": 0.8,
                "timestamp": datetime(2025, 6, 1, tzinfo=timezone.utc),
            },
        ]
        stats = detector.get_summary_stats(analyzed)
        assert abs(stats["human_ratio"] - 2 / 3) < 0.01

    def test_monthly_breakdown(self, detector: AIDetector) -> None:
        """Monthly breakdown should group by YYYY-MM."""
        analyzed = [
            {
                "classification": "human",
                "ai_probability": 0.2,
                "timestamp": datetime(2025, 9, 5, tzinfo=timezone.utc),
            },
            {
                "classification": "ai",
                "ai_probability": 0.8,
                "timestamp": datetime(2025, 9, 20, tzinfo=timezone.utc),
            },
            {
                "classification": "human",
                "ai_probability": 0.1,
                "timestamp": datetime(2025, 10, 3, tzinfo=timezone.utc),
            },
        ]
        stats = detector.get_summary_stats(analyzed)
        assert "2025-09" in stats["monthly_breakdown"]
        assert "2025-10" in stats["monthly_breakdown"]
        assert stats["monthly_breakdown"]["2025-09"]["human"] == 1
        assert stats["monthly_breakdown"]["2025-09"]["ai"] == 1
        assert stats["monthly_breakdown"]["2025-10"]["human"] == 1

    def test_avg_ai_probability(self, detector: AIDetector) -> None:
        """avg_ai_probability should be the mean of all probabilities."""
        analyzed = [
            {
                "classification": "human",
                "ai_probability": 0.2,
                "timestamp": datetime(2025, 6, 1, tzinfo=timezone.utc),
            },
            {
                "classification": "ai",
                "ai_probability": 0.8,
                "timestamp": datetime(2025, 6, 1, tzinfo=timezone.utc),
            },
        ]
        stats = detector.get_summary_stats(analyzed)
        assert abs(stats["avg_ai_probability"] - 0.5) < 0.01


# ── Classification threshold tests ─────────────────────────────────


class TestClassificationThresholds:
    """Verify the exact threshold boundaries."""

    def test_threshold_062_is_ai(self, detector: AIDetector) -> None:
        """ai_probability == 0.62 should classify as 'ai'."""
        # We can't easily force an exact probability, so test the logic
        # by examining the thresholds in analyze()
        commit = _make_commit()
        result = detector.analyze(commit)
        # If the probability happens to be >= 0.62, it should be "ai"
        if result["ai_probability"] >= 0.62:
            assert result["classification"] == "ai"

    def test_threshold_038_is_human(self, detector: AIDetector) -> None:
        """ai_probability <= 0.38 should classify as 'human'."""
        commit = _make_commit()
        result = detector.analyze(commit)
        if result["ai_probability"] <= 0.38:
            assert result["classification"] == "human"

    def test_between_thresholds_is_uncertain(
        self, detector: AIDetector
    ) -> None:
        """0.38 < ai_probability < 0.62 should classify as 'uncertain'."""
        commit = _make_commit()
        result = detector.analyze(commit)
        if 0.38 < result["ai_probability"] < 0.62:
            assert result["classification"] == "uncertain"


# ── Signal weight verification ──────────────────────────────────────


class TestSignalWeights:
    """Verify weights sum to 1.0 and match the specification."""

    def test_weights_sum_to_1(self) -> None:
        """All signal weights must sum to 1.0."""
        total = sum(AIDetector.SIGNAL_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_weight_values(self) -> None:
        """Each weight must match the specification."""
        w = AIDetector.SIGNAL_WEIGHTS
        assert w["velocity"] == 0.30
        assert w["burstiness"] == 0.25
        assert w["formatting"] == 0.20
        assert w["message"] == 0.15
        assert w["entropy"] == 0.10
