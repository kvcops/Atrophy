"""Tests for atrophy.core.storage — async SQLite storage layer.

All tests use in-memory SQLite (``sqlite+aiosqlite:///:memory:``).
Never touches ``~/.atrophy/atrophy.db``.
"""

from datetime import date, datetime, timezone

import pytest

from atrophy.core.storage import (
    Challenge,
    Commit,
    Project,
    SkillSnapshot,
    Storage,
)
from atrophy.exceptions import AtrophyStorageError

# ── Shared fixtures ─────────────────────────────────────────────────

IN_MEMORY_DB = "sqlite+aiosqlite:///:memory:"


@pytest.fixture()
async def storage():
    """Yield an initialized in-memory Storage, then close it."""
    store = Storage(IN_MEMORY_DB)
    await store.init_db()
    yield store
    await store.close()


@pytest.fixture()
async def project(storage: Storage) -> Project:
    """Create and return a sample project."""
    return await storage.save_project(
        path="/tmp/test-repo",
        name="test-repo",
        author_email="dev@example.com",
    )


# ── Project tests ───────────────────────────────────────────────────


class TestProject:
    """Tests for project CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_project_creates_new(self, storage: Storage) -> None:
        """save_project should create a new row when path is new."""
        project = await storage.save_project(
            path="/tmp/my-repo",
            name="my-repo",
            author_email="test@example.com",
        )
        assert project.id is not None
        assert project.name == "my-repo"
        assert project.path == "/tmp/my-repo"
        assert project.author_email == "test@example.com"

    @pytest.mark.asyncio
    async def test_save_project_updates_existing(
        self, storage: Storage
    ) -> None:
        """save_project should update an existing row if path matches."""
        p1 = await storage.save_project("/tmp/repo", "repo-v1")
        p2 = await storage.save_project(
            "/tmp/repo", "repo-v2", author_email="new@example.com"
        )
        # Should be the same row (same id), with updated fields
        assert p2.id == p1.id
        assert p2.name == "repo-v2"
        assert p2.author_email == "new@example.com"

    @pytest.mark.asyncio
    async def test_get_project_found(
        self, storage: Storage, project: Project
    ) -> None:
        """get_project should return the project when it exists."""
        found = await storage.get_project("/tmp/test-repo")
        assert found is not None
        assert found.id == project.id
        assert found.name == "test-repo"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, storage: Storage) -> None:
        """get_project should return None for unknown paths."""
        found = await storage.get_project("/nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_update_last_scanned(
        self, storage: Storage, project: Project
    ) -> None:
        """update_last_scanned should set last_scanned_at to now."""
        assert project.last_scanned_at is None
        await storage.update_last_scanned(project.id)

        refreshed = await storage.get_project("/tmp/test-repo")
        assert refreshed is not None
        assert refreshed.last_scanned_at is not None

    @pytest.mark.asyncio
    async def test_update_last_scanned_nonexistent(
        self, storage: Storage
    ) -> None:
        """update_last_scanned should raise for unknown project ID."""
        with pytest.raises(AtrophyStorageError, match="not found"):
            await storage.update_last_scanned(99999)


# ── Commit tests ────────────────────────────────────────────────────


def _make_commit(
    hash_suffix: str = "a",
    **overrides,
) -> dict:
    """Build a sample commit dict for testing."""
    base = {
        "commit_hash": f"{'0' * 39}{hash_suffix}",
        "timestamp": datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        "message": "feat: add new feature",
        "additions": 50,
        "deletions": 10,
        "ai_probability": 0.3,
        "classification": "human",
        "velocity_score": 0.2,
        "burstiness_score": 0.4,
        "formatting_score": 0.1,
        "message_score": 0.3,
        "entropy_score": 0.5,
    }
    base.update(overrides)
    return base


class TestCommits:
    """Tests for commit upsert operations."""

    @pytest.mark.asyncio
    async def test_upsert_inserts_new(
        self, storage: Storage, project: Project
    ) -> None:
        """New commits should be inserted."""
        commits = [_make_commit("a"), _make_commit("b")]
        count = await storage.upsert_commits(project.id, commits)
        assert count == 2

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(
        self, storage: Storage, project: Project
    ) -> None:
        """Re-upserting the same hash should update scores, not fail."""
        commit_v1 = _make_commit("x", ai_probability=0.3)
        await storage.upsert_commits(project.id, [commit_v1])

        commit_v2 = _make_commit("x", ai_probability=0.9)
        count = await storage.upsert_commits(project.id, [commit_v2])
        assert count == 1

    @pytest.mark.asyncio
    async def test_upsert_empty_list(
        self, storage: Storage, project: Project
    ) -> None:
        """Upserting an empty list should return 0."""
        count = await storage.upsert_commits(project.id, [])
        assert count == 0

    @pytest.mark.asyncio
    async def test_upsert_defaults(
        self, storage: Storage, project: Project
    ) -> None:
        """Commits with missing optional fields should get defaults."""
        minimal = {
            "commit_hash": "a" * 40,
            "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc),
        }
        count = await storage.upsert_commits(project.id, [minimal])
        assert count == 1


# ── Skill snapshot tests ────────────────────────────────────────────


class TestSkillSnapshots:
    """Tests for skill snapshot save and retrieval."""

    @pytest.mark.asyncio
    async def test_save_and_retrieve_latest(
        self, storage: Storage, project: Project
    ) -> None:
        """Skill profiles should be retrievable after saving."""
        profile = {
            "async_concurrency": {
                "score": 75.0,
                "last_seen": datetime(
                    2025, 1, 10, tzinfo=timezone.utc
                ),
                "total_hits": 12,
            },
            "error_handling": {
                "score": 30.0,
                "last_seen": None,
                "total_hits": 3,
            },
        }
        await storage.save_skill_snapshots(project.id, profile)

        latest = await storage.get_all_skills_latest(project.id)
        assert len(latest) == 2
        skill_names = {s.skill_name for s in latest}
        assert "async_concurrency" in skill_names
        assert "error_handling" in skill_names

    @pytest.mark.asyncio
    async def test_save_overwrites_same_day(
        self, storage: Storage, project: Project
    ) -> None:
        """Saving snapshots twice on the same day should update, not duplicate."""
        profile_v1 = {
            "testing": {"score": 50.0, "last_seen": None, "total_hits": 5}
        }
        profile_v2 = {
            "testing": {"score": 80.0, "last_seen": None, "total_hits": 10}
        }
        await storage.save_skill_snapshots(project.id, profile_v1)
        await storage.save_skill_snapshots(project.id, profile_v2)

        latest = await storage.get_all_skills_latest(project.id)
        testing = [s for s in latest if s.skill_name == "testing"]
        assert len(testing) == 1
        assert testing[0].score == 80.0
        assert testing[0].total_hits == 10

    @pytest.mark.asyncio
    async def test_get_skill_history(
        self, storage: Storage, project: Project
    ) -> None:
        """get_skill_history should return snapshots in date order."""
        profile = {
            "algorithms": {
                "score": 60.0,
                "last_seen": None,
                "total_hits": 8,
            }
        }
        await storage.save_skill_snapshots(project.id, profile)

        history = await storage.get_skill_history(
            project.id, "algorithms", months=1
        )
        assert len(history) >= 1
        assert history[0].skill_name == "algorithms"

    @pytest.mark.asyncio
    async def test_get_skill_history_empty(
        self, storage: Storage, project: Project
    ) -> None:
        """get_skill_history should return empty list for unknown skill."""
        history = await storage.get_skill_history(
            project.id, "nonexistent_skill"
        )
        assert history == []


# ── Challenge tests ─────────────────────────────────────────────────


def _make_challenge(**overrides) -> dict:
    """Build a sample challenge dict for testing."""
    base = {
        "skill_name": "error_handling",
        "difficulty": "medium",
        "title": "Build a retry decorator",
        "description": "Create a decorator that retries failed calls.",
    }
    base.update(overrides)
    return base


class TestChallenges:
    """Tests for challenge persistence and completion."""

    @pytest.mark.asyncio
    async def test_save_and_get_pending(
        self, storage: Storage, project: Project
    ) -> None:
        """Saved challenges should appear in pending list."""
        challenges = [
            _make_challenge(title="Challenge 1"),
            _make_challenge(title="Challenge 2"),
        ]
        await storage.save_challenges(project.id, challenges)

        pending = await storage.get_pending_challenges(project.id)
        assert len(pending) == 2
        titles = {c.title for c in pending}
        assert "Challenge 1" in titles
        assert "Challenge 2" in titles

    @pytest.mark.asyncio
    async def test_mark_complete(
        self, storage: Storage, project: Project
    ) -> None:
        """Completing a challenge should remove it from pending."""
        await storage.save_challenges(project.id, [_make_challenge()])
        pending = await storage.get_pending_challenges(project.id)
        assert len(pending) == 1

        challenge_id = pending[0].id
        await storage.mark_challenge_complete(challenge_id)

        pending_after = await storage.get_pending_challenges(project.id)
        assert len(pending_after) == 0

    @pytest.mark.asyncio
    async def test_mark_complete_nonexistent(
        self, storage: Storage
    ) -> None:
        """Completing a nonexistent challenge should raise."""
        with pytest.raises(AtrophyStorageError, match="not found"):
            await storage.mark_challenge_complete(99999)


# ── Settings tests ──────────────────────────────────────────────────


class TestSettings:
    """Tests for the key-value settings store."""

    @pytest.mark.asyncio
    async def test_set_and_get(self, storage: Storage) -> None:
        """set_setting then get_setting should return the value."""
        await storage.set_setting("theme", "dark")
        value = await storage.get_setting("theme")
        assert value == "dark"

    @pytest.mark.asyncio
    async def test_get_default(self, storage: Storage) -> None:
        """get_setting for unknown key should return the default."""
        value = await storage.get_setting("nonexistent", default="fallback")
        assert value == "fallback"

    @pytest.mark.asyncio
    async def test_get_none_default(self, storage: Storage) -> None:
        """get_setting for unknown key with no default returns None."""
        value = await storage.get_setting("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_update_existing(self, storage: Storage) -> None:
        """set_setting should update if the key already exists."""
        await storage.set_setting("lang", "en")
        await storage.set_setting("lang", "fr")
        value = await storage.get_setting("lang")
        assert value == "fr"


# ── Init and error handling ─────────────────────────────────────────


class TestInitAndErrors:
    """Tests for database initialization and error wrapping."""

    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self) -> None:
        """init_db should create all tables without errors."""
        store = Storage(IN_MEMORY_DB)
        await store.init_db()
        # Verify we can write to every table
        project = await store.save_project("/tmp/init-test", "init-test")
        assert project.id is not None
        await store.close()

    @pytest.mark.asyncio
    async def test_double_init_is_safe(self) -> None:
        """Calling init_db twice should not raise."""
        store = Storage(IN_MEMORY_DB)
        await store.init_db()
        await store.init_db()  # Should be idempotent
        await store.close()
