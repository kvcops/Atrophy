"""Tests for atrophy.core.skill_mapper — skill categorization.

Verifies keyword matching, recency weighting, dead zone detection,
trend computation, monthly breakdown, and coding DNA profiling.
"""

from datetime import datetime, timedelta, timezone

import pytest

from atrophy.core.skill_mapper import SKILL_PATTERNS, SkillMapper


# ── Fixtures and helpers ────────────────────────────────────────────


@pytest.fixture()
def mapper() -> SkillMapper:
    """Return a fresh SkillMapper instance."""
    return SkillMapper()


def _make_commit(
    diff_text: str = "",
    files_changed: list[str] | None = None,
    ai_probability: float = 0.2,
    classification: str = "human",
    additions: int = 20,
    timestamp: datetime | None = None,
    **overrides,
) -> dict:
    """Build a minimal analyzed commit dict for testing."""
    base: dict = {
        "commit_hash": "a" * 40,
        "author_name": "Dev",
        "author_email": "dev@example.com",
        "timestamp": timestamp
        or datetime.now(timezone.utc) - timedelta(days=5),
        "message": "feat: testing",
        "files_changed": files_changed or ["main.py"],
        "additions": additions,
        "deletions": 2,
        "diff_text": diff_text,
        "minutes_since_prev": 10.0,
        "session_additions": additions,
        "ai_probability": ai_probability,
        "classification": classification,
        "velocity_score": 0.3,
        "burstiness_score": 0.4,
        "formatting_score": 0.3,
        "message_score": 0.4,
        "entropy_score": 0.5,
    }
    base.update(overrides)
    return base


def _recent(days: int = 5) -> datetime:
    """Return a UTC datetime N days ago."""
    return datetime.now(timezone.utc) - timedelta(days=days)


def _old(days: int = 120) -> datetime:
    """Return a UTC datetime N days ago (old)."""
    return datetime.now(timezone.utc) - timedelta(days=days)


# ── Skill patterns structure tests ──────────────────────────────────


class TestSkillPatterns:
    """Verify SKILL_PATTERNS structure is valid."""

    def test_has_10_skills(self) -> None:
        """There should be exactly 10 skill categories."""
        assert len(SKILL_PATTERNS) == 10

    def test_canonical_keys(self) -> None:
        """The 10 canonical skill keys must all be present."""
        expected = {
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
        }
        assert set(SKILL_PATTERNS.keys()) == expected

    def test_each_skill_has_required_fields(self) -> None:
        """Every skill must have keywords, file_extensions, description, emoji."""
        for name, pattern in SKILL_PATTERNS.items():
            assert "keywords" in pattern, f"{name} missing keywords"
            assert "file_extensions" in pattern, f"{name} missing file_extensions"
            assert "description" in pattern, f"{name} missing description"
            assert "emoji" in pattern, f"{name} missing emoji"
            assert len(pattern["keywords"]) > 0, f"{name} has empty keywords"


# ── map_skills tests ────────────────────────────────────────────────


class TestMapSkills:
    """Tests for the main map_skills() method."""

    def test_empty_commits(self, mapper: SkillMapper) -> None:
        """Empty commit list should return all skills with score 0."""
        profile = mapper.map_skills([])
        assert len(profile) == 10
        for data in profile.values():
            assert data["score"] == 0.0
            assert data["total_hits"] == 0

    def test_ai_commits_filtered_out(self, mapper: SkillMapper) -> None:
        """Commits with ai_probability >= 0.55 should be ignored."""
        ai_commit = _make_commit(
            diff_text="async def main():\n    await fetch()\n",
            ai_probability=0.7,
            classification="ai",
        )
        profile = mapper.map_skills([ai_commit])
        assert profile["async_concurrency"]["total_hits"] == 0

    def test_human_commit_counted(self, mapper: SkillMapper) -> None:
        """Human commits should produce hits in matching skills."""
        commit = _make_commit(
            diff_text="async def main():\n    await fetch()\n",
            ai_probability=0.2,
        )
        profile = mapper.map_skills([commit])
        assert profile["async_concurrency"]["total_hits"] > 0
        assert profile["async_concurrency"]["score"] > 0

    def test_multiple_skills_from_one_commit(
        self, mapper: SkillMapper
    ) -> None:
        """A single commit can hit multiple skills."""
        commit = _make_commit(
            diff_text=(
                "async def handler():\n"
                "    try:\n"
                "        result = await db.query()\n"
                "    except Exception:\n"
                "        raise\n"
            ),
            ai_probability=0.1,
        )
        profile = mapper.map_skills([commit])
        # Should hit async_concurrency, error_handling at minimum
        assert profile["async_concurrency"]["total_hits"] > 0
        assert profile["error_handling"]["total_hits"] > 0

    def test_recency_weight_recent(self, mapper: SkillMapper) -> None:
        """Commits in the last 30 days should get 3x weighting."""
        commit = _make_commit(
            diff_text="try:\n    pass\nexcept:\n    pass\n",
            timestamp=_recent(5),
            ai_probability=0.1,
        )
        profile = mapper.map_skills([commit])
        # 'try:' and 'except ' = 2 hits * 3.0x = 6.0 weighted → 6.0 * 2.5 = 15.0
        assert profile["error_handling"]["score"] > 0

    def test_recency_weight_old(self, mapper: SkillMapper) -> None:
        """Commits older than 90 days should get 1x weighting."""
        commit_old = _make_commit(
            diff_text="try:\n    pass\nexcept:\n    pass\n",
            timestamp=_old(120),
            ai_probability=0.1,
        )
        commit_recent = _make_commit(
            diff_text="try:\n    pass\nexcept:\n    pass\n",
            timestamp=_recent(5),
            ai_probability=0.1,
        )
        profile_old = mapper.map_skills([commit_old])
        profile_recent = mapper.map_skills([commit_recent])

        # Same raw hits, but recent should have higher score (3x vs 1x)
        assert (
            profile_recent["error_handling"]["score"]
            > profile_old["error_handling"]["score"]
        )

    def test_score_capped_at_100(self, mapper: SkillMapper) -> None:
        """Scores should never exceed 100."""
        # Create a commit with tons of keyword hits
        big_diff = "async def f():\n    await x\n" * 100
        commit = _make_commit(
            diff_text=big_diff, ai_probability=0.1, timestamp=_recent(1)
        )
        profile = mapper.map_skills([commit])
        assert profile["async_concurrency"]["score"] <= 100.0

    def test_last_seen_tracked(self, mapper: SkillMapper) -> None:
        """last_seen should be the most recent commit timestamp."""
        ts1 = _recent(10)
        ts2 = _recent(5)
        commits = [
            _make_commit(diff_text="try:\nraise ValueError\n", timestamp=ts1),
            _make_commit(diff_text="except Exception:\nraise\n", timestamp=ts2),
        ]
        profile = mapper.map_skills(commits)
        assert profile["error_handling"]["last_seen"] == ts2

    def test_recent_hits_counted(self, mapper: SkillMapper) -> None:
        """recent_hits should only count hits from the last 30 days."""
        # One recent, one old
        commits = [
            _make_commit(
                diff_text="try:\n    pass\n",
                timestamp=_recent(5),
            ),
            _make_commit(
                diff_text="try:\n    pass\n",
                timestamp=_old(120),
            ),
        ]
        profile = mapper.map_skills(commits)
        # Only the recent commit's hits should count
        assert profile["error_handling"]["recent_hits"] >= 1

    def test_file_extension_filtering(self, mapper: SkillMapper) -> None:
        """Skills should only match files with relevant extensions."""
        # SQL hit in a .py file → should match
        commit_py = _make_commit(
            diff_text="SELECT * FROM users WHERE id = 1",
            files_changed=["query.py"],
        )
        # SQL hit in a .svg file → should NOT match (not in sql_databases exts)
        commit_svg = _make_commit(
            diff_text="SELECT * FROM users WHERE id = 1",
            files_changed=["image.svg"],
        )
        profile_py = mapper.map_skills([commit_py])
        profile_svg = mapper.map_skills([commit_svg])

        assert profile_py["sql_databases"]["total_hits"] > 0
        assert profile_svg["sql_databases"]["total_hits"] == 0

    def test_profile_has_all_required_fields(
        self, mapper: SkillMapper
    ) -> None:
        """Each skill profile entry must have all required fields."""
        commit = _make_commit(diff_text="pass")
        profile = mapper.map_skills([commit])
        required = {
            "score", "last_seen", "total_hits", "recent_hits",
            "trend", "description", "emoji",
        }
        for skill_name, data in profile.items():
            missing = required - set(data.keys())
            assert missing == set(), f"{skill_name} missing: {missing}"


# ── Keyword matching tests ──────────────────────────────────────────


class TestKeywordMatching:
    """Tests for the _count_keyword_hits helper."""

    def test_exact_keyword_match(self) -> None:
        """Simple keywords should be found by substring match."""
        hits = SkillMapper._count_keyword_hits(
            "async def main():\n    await fetch()",
            ["async def ", "await "],
        )
        assert hits == 2

    def test_wildcard_pattern(self) -> None:
        """Keywords with .* should match across the line."""
        hits = SkillMapper._count_keyword_hits(
            "class MyCustomError(Exception):",
            ["class.*Error"],
        )
        assert hits == 1

    def test_no_match_returns_zero(self) -> None:
        """Unmatched keywords should return 0."""
        hits = SkillMapper._count_keyword_hits(
            "print('hello world')",
            ["async def ", "await "],
        )
        assert hits == 0


# ── Dead zone tests ─────────────────────────────────────────────────


class TestDeadZones:
    """Tests for get_dead_zones()."""

    def test_never_used_is_dead(self, mapper: SkillMapper) -> None:
        """Skills with last_seen=None should be in dead zones."""
        profile = {
            "testing": {
                "score": 0.0,
                "last_seen": None,
                "total_hits": 0,
                "recent_hits": 0,
                "trend": "new",
                "description": "",
                "emoji": "",
            },
        }
        dead = mapper.get_dead_zones(profile)
        assert "testing" in dead

    def test_old_skill_is_dead(self, mapper: SkillMapper) -> None:
        """Skills last seen > threshold_days ago should be dead."""
        profile = {
            "testing": {
                "score": 50.0,
                "last_seen": _old(60),
                "total_hits": 20,
                "recent_hits": 0,
                "trend": "down",
                "description": "",
                "emoji": "",
            },
        }
        dead = mapper.get_dead_zones(profile, threshold_days=45)
        assert "testing" in dead

    def test_low_score_is_dead(self, mapper: SkillMapper) -> None:
        """Skills with score < 8 should be dead even if recent."""
        profile = {
            "testing": {
                "score": 5.0,
                "last_seen": _recent(2),
                "total_hits": 1,
                "recent_hits": 1,
                "trend": "stable",
                "description": "",
                "emoji": "",
            },
        }
        dead = mapper.get_dead_zones(profile)
        assert "testing" in dead

    def test_active_skill_not_dead(self, mapper: SkillMapper) -> None:
        """Recently used skills with decent score should not be dead."""
        profile = {
            "testing": {
                "score": 50.0,
                "last_seen": _recent(5),
                "total_hits": 20,
                "recent_hits": 5,
                "trend": "up",
                "description": "",
                "emoji": "",
            },
        }
        dead = mapper.get_dead_zones(profile)
        assert "testing" not in dead

    def test_dead_zones_sorted_by_urgency(self, mapper: SkillMapper) -> None:
        """Dead zones should be sorted: oldest first, None last."""
        profile = {
            "testing": {
                "score": 0, "last_seen": None,
                "total_hits": 0, "recent_hits": 0,
                "trend": "new", "description": "", "emoji": "",
            },
            "security": {
                "score": 5, "last_seen": _old(100),
                "total_hits": 2, "recent_hits": 0,
                "trend": "down", "description": "", "emoji": "",
            },
            "algorithms": {
                "score": 3, "last_seen": _old(60),
                "total_hits": 1, "recent_hits": 0,
                "trend": "down", "description": "", "emoji": "",
            },
        }
        dead = mapper.get_dead_zones(profile)
        # security (100 days ago) before algorithms (60 days ago) before testing (None)
        assert dead.index("security") < dead.index("algorithms")
        assert dead.index("algorithms") < dead.index("testing")


# ── Strongest skills tests ──────────────────────────────────────────


class TestStrongestSkills:
    """Tests for get_strongest_skills()."""

    def test_top_3_by_score(self, mapper: SkillMapper) -> None:
        """Should return the 3 highest-scoring skills."""
        profile = {
            "testing": {"score": 90},
            "security": {"score": 70},
            "error_handling": {"score": 80},
            "algorithms": {"score": 10},
        }
        top = mapper.get_strongest_skills(profile, top_n=3)
        assert top == ["testing", "error_handling", "security"]

    def test_custom_top_n(self, mapper: SkillMapper) -> None:
        """top_n parameter should control the count."""
        profile = {
            "a": {"score": 100},
            "b": {"score": 50},
            "c": {"score": 25},
        }
        assert len(mapper.get_strongest_skills(profile, top_n=1)) == 1
        assert len(mapper.get_strongest_skills(profile, top_n=2)) == 2


# ── Trend computation tests ────────────────────────────────────────


class TestTrendComputation:
    """Tests for _compute_trend()."""

    def test_no_hits_is_new(self) -> None:
        """Zero total hits → 'new'."""
        assert SkillMapper._compute_trend(0, 0, 0) == "new"

    def test_only_recent_is_up(self) -> None:
        """Hits only in month 1 (no month 2) → 'up'."""
        assert SkillMapper._compute_trend(5, 0, 5) == "up"

    def test_only_old_is_down(self) -> None:
        """Hits only in month 2 (no month 1) → 'down'."""
        assert SkillMapper._compute_trend(0, 5, 5) == "down"

    def test_significant_increase_is_up(self) -> None:
        """25%+ increase → 'up'."""
        assert SkillMapper._compute_trend(10, 5, 15) == "up"

    def test_significant_decrease_is_down(self) -> None:
        """25%+ decrease → 'down'."""
        assert SkillMapper._compute_trend(3, 10, 13) == "down"

    def test_stable_ratio(self) -> None:
        """Within 25% → 'stable'."""
        assert SkillMapper._compute_trend(10, 10, 20) == "stable"


# ── Coding DNA tests ───────────────────────────────────────────────


class TestCodingDNA:
    """Tests for get_coding_dna()."""

    def test_structure(self, mapper: SkillMapper) -> None:
        """Coding DNA should have all required keys."""
        commits = [_make_commit(files_changed=["app.py"])]
        profile = mapper.map_skills(commits)
        dna = mapper.get_coding_dna(commits, profile)

        required = {
            "primary_language",
            "top_skills",
            "dead_zones",
            "ai_ratio",
            "avg_commit_size",
            "coding_style",
            "most_productive_hour",
        }
        assert required == set(dna.keys())

    def test_primary_language(self, mapper: SkillMapper) -> None:
        """Primary language should be the most common extension."""
        commits = [
            _make_commit(files_changed=["a.py", "b.py", "c.ts"]),
        ]
        profile = mapper.map_skills(commits)
        dna = mapper.get_coding_dna(commits, profile)
        assert dna["primary_language"] == "py"

    def test_coding_style_precise(self, mapper: SkillMapper) -> None:
        """Low AI ratio + small commits → 'precise'."""
        commits = [
            _make_commit(
                additions=10, ai_probability=0.1, classification="human"
            )
        ]
        profile = mapper.map_skills(commits)
        dna = mapper.get_coding_dna(commits, profile)
        assert dna["coding_style"] == "precise"

    def test_coding_style_methodical(self, mapper: SkillMapper) -> None:
        """Low AI ratio + larger commits → 'methodical'."""
        commits = [
            _make_commit(
                additions=50, ai_probability=0.1, classification="human"
            )
        ]
        profile = mapper.map_skills(commits)
        dna = mapper.get_coding_dna(commits, profile)
        assert dna["coding_style"] == "methodical"

    def test_coding_style_ai_augmented(self, mapper: SkillMapper) -> None:
        """High AI ratio (>= 0.5) → 'ai-augmented'."""
        commits = [
            _make_commit(classification="ai"),
            _make_commit(classification="ai"),
            _make_commit(classification="human"),
            _make_commit(classification="ai"),
        ]
        profile = mapper.map_skills(commits)
        dna = mapper.get_coding_dna(commits, profile)
        assert dna["coding_style"] == "ai-augmented"

    def test_most_productive_hour(self, mapper: SkillMapper) -> None:
        """Most productive hour should be the most common hour."""
        hour_10 = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
        hour_14 = datetime(2025, 6, 15, 14, 0, 0, tzinfo=timezone.utc)
        commits = [
            _make_commit(timestamp=hour_10),
            _make_commit(timestamp=hour_10),
            _make_commit(timestamp=hour_14),
        ]
        profile = mapper.map_skills(commits)
        dna = mapper.get_coding_dna(commits, profile)
        assert dna["most_productive_hour"] == 10


# ── Monthly skill scores tests ─────────────────────────────────────


class TestMonthlySkillScores:
    """Tests for get_monthly_skill_scores()."""

    def test_unknown_skill_returns_empty(self, mapper: SkillMapper) -> None:
        """Unknown skill names should return empty list."""
        result = mapper.get_monthly_skill_scores([], "nonexistent")
        assert result == []

    def test_months_with_no_hits_score_zero(
        self, mapper: SkillMapper
    ) -> None:
        """Months with no qualifying commits should score 0."""
        result = mapper.get_monthly_skill_scores(
            [], "error_handling", months=3
        )
        assert all(entry["score"] == 0.0 for entry in result)

    def test_months_sorted_chronologically(
        self, mapper: SkillMapper
    ) -> None:
        """Results should be sorted by month ascending."""
        result = mapper.get_monthly_skill_scores(
            [], "testing", months=4
        )
        months = [entry["month"] for entry in result]
        assert months == sorted(months)
