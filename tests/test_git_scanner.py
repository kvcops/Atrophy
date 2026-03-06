"""Tests for atrophy.core.git_scanner — git history scanning.

All tests mock GitPython objects to avoid depending on real repos.
Uses tmp_path for filesystem tests.
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from atrophy.core.git_scanner import (
    EXCLUDE_PATTERNS,
    GitScanner,
)
from atrophy.exceptions import AtrophyGitError


# ── Fixtures and helpers ────────────────────────────────────────────


def _make_mock_repo(tmp_path: Path) -> MagicMock:
    """Create a minimal mock Repo that passes validation."""
    mock_repo = MagicMock()
    mock_repo.bare = False
    return mock_repo


def _make_mock_commit(
    hexsha: str = "a" * 40,
    author_name: str = "Test Dev",
    author_email: str = "dev@example.com",
    message: str = "feat: test commit",
    committed_datetime: datetime | None = None,
    parents: list | None = None,
    diffs: list | None = None,
) -> MagicMock:
    """Build a mock GitPython Commit object."""
    commit = MagicMock()
    commit.hexsha = hexsha
    commit.author.name = author_name
    commit.author.email = author_email
    commit.message = message
    commit.committed_datetime = committed_datetime or datetime(
        2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc
    )

    if parents is None:
        parent = MagicMock()
        parent.diff.return_value = diffs or []
        commit.parents = [parent]
    else:
        commit.parents = parents

    commit.diff.return_value = diffs or []
    return commit


def _make_mock_diff(
    file_path: str = "src/main.py",
    patch_text: str = "+def hello():\n+    pass\n",
) -> MagicMock:
    """Build a mock GitPython Diff object."""
    diff = MagicMock()
    diff.a_path = file_path
    diff.b_path = file_path
    diff.diff = patch_text.encode("utf-8")
    return diff


# ── Initialization tests ───────────────────────────────────────────


class TestGitScannerInit:
    """Tests for GitScanner.__init__ validation."""

    def test_nonexistent_path_raises(self, tmp_path: Path) -> None:
        """A path that doesn't exist should raise AtrophyGitError."""
        fake_path = tmp_path / "nonexistent_repo"
        with pytest.raises(AtrophyGitError, match="does not exist"):
            GitScanner(fake_path)

    def test_file_path_raises(self, tmp_path: Path) -> None:
        """A file (not directory) should raise AtrophyGitError."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("hello")
        with pytest.raises(AtrophyGitError, match="not a directory"):
            GitScanner(file_path)

    @patch("atrophy.core.git_scanner.Repo")
    def test_non_git_dir_raises(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """A directory that's not a git repo should raise AtrophyGitError."""
        from git import InvalidGitRepositoryError

        mock_repo_cls.side_effect = InvalidGitRepositoryError("not a repo")
        with pytest.raises(AtrophyGitError, match="Not a valid git"):
            GitScanner(tmp_path)

    @patch("atrophy.core.git_scanner.Repo")
    def test_bare_repo_raises(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """A bare repo should raise AtrophyGitError."""
        mock_repo = MagicMock()
        mock_repo.bare = True
        mock_repo_cls.return_value = mock_repo
        with pytest.raises(AtrophyGitError, match="bare repository"):
            GitScanner(tmp_path)

    def test_invalid_email_raises(self, tmp_path: Path) -> None:
        """An invalid author_email should raise ValueError."""
        # We don't even get to the Repo check — email is validated
        # after path. But for this test, let's use a path that exists
        # and mock the Repo.
        with patch("atrophy.core.git_scanner.Repo") as mock_cls:
            mock_cls.return_value = _make_mock_repo(tmp_path)
            with pytest.raises(ValueError, match="Invalid author email"):
                GitScanner(tmp_path, author_email="not-an-email")

    @patch("atrophy.core.git_scanner.Repo")
    def test_valid_email_accepted(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """A valid email should be accepted without raising."""
        mock_repo_cls.return_value = _make_mock_repo(tmp_path)
        scanner = GitScanner(
            tmp_path, author_email="dev@example.com"
        )
        assert scanner._author_email == "dev@example.com"

    @patch("atrophy.core.git_scanner.Repo")
    def test_none_email_accepted(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """None email (the default) should be valid."""
        mock_repo_cls.return_value = _make_mock_repo(tmp_path)
        scanner = GitScanner(tmp_path)
        assert scanner._author_email is None


# ── scan_commits tests ──────────────────────────────────────────────


class TestScanCommits:
    """Tests for the main scan_commits method."""

    @patch("atrophy.core.git_scanner.Repo")
    def test_empty_repo_returns_empty(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """A repo with no commits should return an empty list."""
        mock_repo = _make_mock_repo(tmp_path)
        mock_repo.iter_commits.return_value = []
        mock_repo_cls.return_value = mock_repo

        scanner = GitScanner(tmp_path)
        result = scanner.scan_commits()
        assert result == []

    @patch("atrophy.core.git_scanner.Repo")
    def test_basic_commit_extraction(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """A single valid commit should produce one result dict."""
        diff = _make_mock_diff("src/app.py", "+print('hello')\n")
        commit = _make_mock_commit(diffs=[diff])

        mock_repo = _make_mock_repo(tmp_path)
        mock_repo.iter_commits.return_value = [commit]
        mock_repo_cls.return_value = mock_repo

        scanner = GitScanner(tmp_path, days_back=365)
        results = scanner.scan_commits()
        assert len(results) == 1

        r = results[0]
        assert r["commit_hash"] == "a" * 40
        assert r["author_name"] == "Test Dev"
        assert r["author_email"] == "dev@example.com"
        assert r["message"] == "feat: test commit"
        assert "src/app.py" in r["files_changed"]
        assert r["additions"] >= 1
        assert isinstance(r["timestamp"], datetime)
        assert isinstance(r["diff_text"], str)
        assert isinstance(r["minutes_since_prev"], float)
        assert isinstance(r["session_additions"], int)

    @patch("atrophy.core.git_scanner.Repo")
    def test_merge_commits_skipped(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """Merge commits (>1 parent) should be filtered out."""
        parent1 = MagicMock()
        parent2 = MagicMock()
        commit = _make_mock_commit(parents=[parent1, parent2])

        mock_repo = _make_mock_repo(tmp_path)
        mock_repo.iter_commits.return_value = [commit]
        mock_repo_cls.return_value = mock_repo

        scanner = GitScanner(tmp_path, days_back=365)
        results = scanner.scan_commits()
        assert len(results) == 0

    @patch("atrophy.core.git_scanner.Repo")
    def test_author_email_filter(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """Only commits matching author_email should be included."""
        diff = _make_mock_diff("file.py", "+code\n")
        commit_match = _make_mock_commit(
            hexsha="a" * 40,
            author_email="me@example.com",
            diffs=[diff],
        )
        commit_other = _make_mock_commit(
            hexsha="b" * 40,
            author_email="other@example.com",
            diffs=[diff],
        )

        mock_repo = _make_mock_repo(tmp_path)
        mock_repo.iter_commits.return_value = [commit_match, commit_other]
        mock_repo_cls.return_value = mock_repo

        scanner = GitScanner(
            tmp_path, days_back=365, author_email="me@example.com"
        )
        results = scanner.scan_commits()
        assert len(results) == 1
        assert results[0]["author_email"] == "me@example.com"

    @patch("atrophy.core.git_scanner.Repo")
    def test_author_email_case_insensitive(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """Email filter should be case-insensitive."""
        diff = _make_mock_diff("file.py", "+code\n")
        commit = _make_mock_commit(
            author_email="Dev@Example.COM", diffs=[diff]
        )

        mock_repo = _make_mock_repo(tmp_path)
        mock_repo.iter_commits.return_value = [commit]
        mock_repo_cls.return_value = mock_repo

        scanner = GitScanner(
            tmp_path, days_back=365, author_email="dev@example.com"
        )
        results = scanner.scan_commits()
        assert len(results) == 1


# ── File exclusion tests ────────────────────────────────────────────


class TestFileExclusion:
    """Tests for the _should_exclude_file static method."""

    def test_lockfiles_excluded(self) -> None:
        """Lock files should be excluded."""
        assert GitScanner._should_exclude_file("package-lock.json", "package-lock.json")
        assert GitScanner._should_exclude_file("yarn.lock", "yarn.lock")
        assert GitScanner._should_exclude_file("Pipfile.lock", "Pipfile.lock")
        assert GitScanner._should_exclude_file("poetry.lock", "poetry.lock")
        assert GitScanner._should_exclude_file("uv.lock", "uv.lock")

    def test_minified_files_excluded(self) -> None:
        """Minified JS/CSS should be excluded."""
        assert GitScanner._should_exclude_file("app.min.js", "app.min.js")
        assert GitScanner._should_exclude_file("style.min.css", "style.min.css")

    def test_pycache_excluded(self) -> None:
        """__pycache__ and .pyc files should be excluded."""
        assert GitScanner._should_exclude_file(
            "__pycache__/module.cpython-311.pyc", "module.cpython-311.pyc"
        )
        assert GitScanner._should_exclude_file("cache.pyc", "cache.pyc")

    def test_dist_build_excluded(self) -> None:
        """dist/ and build/ directories should be excluded."""
        assert GitScanner._should_exclude_file("dist/bundle.js", "bundle.js")
        assert GitScanner._should_exclude_file("build/output.js", "output.js")

    def test_node_modules_excluded(self) -> None:
        """node_modules/ should be excluded."""
        assert GitScanner._should_exclude_file(
            "node_modules/lodash/index.js", "index.js"
        )

    def test_migrations_excluded(self) -> None:
        """migrations/ directory should be excluded."""
        assert GitScanner._should_exclude_file(
            "migrations/0001_initial.py", "0001_initial.py"
        )

    def test_normal_files_not_excluded(self) -> None:
        """Normal source files should NOT be excluded."""
        assert not GitScanner._should_exclude_file("src/main.py", "main.py")
        assert not GitScanner._should_exclude_file("app.ts", "app.ts")
        assert not GitScanner._should_exclude_file(
            "tests/test_foo.py", "test_foo.py"
        )

    def test_env_excluded(self) -> None:
        """.env file should be excluded."""
        assert GitScanner._should_exclude_file(".env", ".env")


# ── Language breakdown tests ────────────────────────────────────────


class TestLanguageBreakdown:
    """Tests for get_language_breakdown and detect_primary_language."""

    @patch("atrophy.core.git_scanner.Repo")
    def test_language_breakdown(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """Should count file extensions correctly."""
        mock_repo_cls.return_value = _make_mock_repo(tmp_path)
        scanner = GitScanner(tmp_path)

        commits = [
            {
                "files_changed": [
                    "a.py", "b.py", "c.ts", "d.py", "e.lock"
                ]
            },
            {"files_changed": ["f.ts", "g.py"]},
        ]
        breakdown = scanner.get_language_breakdown(commits)
        assert breakdown["py"] == 4
        assert breakdown["ts"] == 2
        # .lock should be skipped
        assert "lock" not in breakdown

    @patch("atrophy.core.git_scanner.Repo")
    def test_detect_primary_language(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """Should return the most common extension."""
        mock_repo_cls.return_value = _make_mock_repo(tmp_path)
        scanner = GitScanner(tmp_path)

        commits = [
            {"files_changed": ["a.py", "b.ts", "c.py"]},
        ]
        assert scanner.detect_primary_language(commits) == "py"

    @patch("atrophy.core.git_scanner.Repo")
    def test_detect_primary_language_default(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """Should default to 'python' when no files."""
        mock_repo_cls.return_value = _make_mock_repo(tmp_path)
        scanner = GitScanner(tmp_path)

        assert scanner.detect_primary_language([]) == "python"


# ── Data contract validation ────────────────────────────────────────


class TestDataContract:
    """Verify the exact shape of commit dicts."""

    REQUIRED_KEYS = {
        "commit_hash",
        "author_name",
        "author_email",
        "timestamp",
        "message",
        "files_changed",
        "additions",
        "deletions",
        "diff_text",
        "minutes_since_prev",
        "session_additions",
    }

    @patch("atrophy.core.git_scanner.Repo")
    def test_commit_dict_has_all_required_keys(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """Each result dict must contain all contract-specified keys."""
        diff = _make_mock_diff("src/app.py", "+line1\n+line2\n")
        commit = _make_mock_commit(diffs=[diff])

        mock_repo = _make_mock_repo(tmp_path)
        mock_repo.iter_commits.return_value = [commit]
        mock_repo_cls.return_value = mock_repo

        scanner = GitScanner(tmp_path, days_back=365)
        results = scanner.scan_commits()
        assert len(results) == 1

        result = results[0]
        missing = self.REQUIRED_KEYS - set(result.keys())
        assert missing == set(), f"Missing keys: {missing}"

    @patch("atrophy.core.git_scanner.Repo")
    def test_commit_hash_is_40_chars(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """commit_hash should be exactly 40 hex characters."""
        diff = _make_mock_diff("f.py", "+code\n")
        commit = _make_mock_commit(hexsha="ab12cd34" * 5, diffs=[diff])

        mock_repo = _make_mock_repo(tmp_path)
        mock_repo.iter_commits.return_value = [commit]
        mock_repo_cls.return_value = mock_repo

        scanner = GitScanner(tmp_path, days_back=365)
        results = scanner.scan_commits()
        assert len(results[0]["commit_hash"]) == 40

    @patch("atrophy.core.git_scanner.Repo")
    def test_timestamp_is_utc_aware(
        self, mock_repo_cls: MagicMock, tmp_path: Path
    ) -> None:
        """timestamp must be timezone-aware UTC."""
        diff = _make_mock_diff("f.py", "+x\n")
        commit = _make_mock_commit(diffs=[diff])

        mock_repo = _make_mock_repo(tmp_path)
        mock_repo.iter_commits.return_value = [commit]
        mock_repo_cls.return_value = mock_repo

        scanner = GitScanner(tmp_path, days_back=365)
        results = scanner.scan_commits()
        ts = results[0]["timestamp"]
        assert ts.tzinfo is not None
