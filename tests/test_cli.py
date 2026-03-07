"""Tests for the CLI commands: init, scan, and report.

Tests verify that the commands work end-to-end using mocked
dependencies (storage, git scanner, AI detector, skill mapper).
All tests use in-memory storage or mocks — never touch ~/.atrophy/.
"""

import json
import subprocess
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from atrophy.cli.app import app

runner = CliRunner()


# ── Fixtures ────────────────────────────────────────────────────────


def _make_project(
    project_id: int = 1,
    name: str = "test-project",
    path: str = ".",
    author_email: str = "dev@example.com",
    last_scanned_at: datetime | None = None,
):
    """Create a mock Project ORM object."""
    project = MagicMock()
    project.id = project_id
    project.name = name
    project.path = path
    project.author_email = author_email
    project.last_scanned_at = last_scanned_at
    return project


def _make_skill_snapshot(
    skill_name: str = "testing",
    score: float = 50.0,
    last_seen: datetime | None = None,
    total_hits: int = 10,
):
    """Create a mock SkillSnapshot ORM object."""
    snap = MagicMock()
    snap.skill_name = skill_name
    snap.score = score
    snap.last_seen = last_seen or datetime(2025, 1, 1, tzinfo=UTC)
    snap.total_hits = total_hits
    return snap


def _make_analyzed_commits(count: int = 10) -> list[dict]:
    """Create a list of analyzed commit dicts."""
    commits = []
    for i in range(count):
        classification = "human" if i % 3 != 0 else "ai"
        commits.append({
            "commit_hash": f"{'a' * 39}{i}",
            "author_name": "Dev",
            "author_email": "dev@example.com",
            "timestamp": datetime(2025, 1, 15, tzinfo=UTC),
            "message": f"commit {i}",
            "files_changed": ["test.py"],
            "additions": 10,
            "deletions": 2,
            "diff_text": "+    x = 1\n",
            "minutes_since_prev": 5.0,
            "session_additions": 10,
            "ai_probability": 0.2 if classification == "human" else 0.8,
            "classification": classification,
            "velocity_score": 0.3,
            "burstiness_score": 0.4,
            "formatting_score": 0.3,
            "message_score": 0.2,
            "entropy_score": 0.3,
        })
    return commits


# ── Tests: atrophy --version ────────────────────────────────────────


class TestVersion:
    """Test the --version flag."""

    def test_version_flag(self) -> None:
        """--version prints version and exits cleanly."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "atrophy" in result.output


# ── Tests: atrophy init ────────────────────────────────────────────


class TestInit:
    """Tests for the init command."""

    @patch("atrophy.cli.app._get_storage")
    @patch("atrophy.cli.app.get_settings")
    @patch("atrophy.cli.app._detect_email")
    @patch("atrophy.cli.onboarding.run_onboarding")
    def test_init_not_git_repo(
        self, mock_onboarding, mock_email, mock_settings, mock_storage,
        tmp_path,
    ) -> None:
        """init fails with error if not in a git repo."""
        import os

        os.chdir(tmp_path)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 1
        assert "Not a git repository" in result.output

    @patch("atrophy.cli.app._get_storage")
    @patch("atrophy.cli.app.get_settings")
    @patch("atrophy.cli.app._detect_email")
    @patch("atrophy.cli.onboarding.run_onboarding")
    @patch("atrophy.cli.onboarding.ask_auto_scan_hook")
    def test_init_success(
        self, mock_ask_hook, mock_onboarding, mock_email, mock_settings, mock_storage,
        tmp_path,
    ) -> None:
        """init succeeds in a git repo with valid email."""
        import os

        subprocess.run(  # noqa: S603
            ["git", "init", str(tmp_path)],  # noqa: S607
            capture_output=True,
            shell=False,
            timeout=10,
        )
        os.chdir(tmp_path)

        mock_email.return_value = "dev@example.com"

        # Mock storage
        storage_instance = AsyncMock()
        storage_instance.init_db = AsyncMock()
        storage_instance.save_project = AsyncMock(
            return_value=_make_project()
        )
        storage_instance.close = AsyncMock()
        mock_storage.return_value = storage_instance

        # Mock settings
        settings_instance = MagicMock()
        settings_instance.data_dir = tmp_path / ".atrophy"
        settings_instance.save = MagicMock()
        mock_settings.return_value = settings_instance

        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "atrophy initialized" in result.output

    @patch("atrophy.cli.app._get_storage")
    @patch("atrophy.cli.app.get_settings")
    @patch("atrophy.cli.app._detect_email")
    @patch("atrophy.cli.onboarding.run_onboarding")
    def test_init_invalid_email(
        self, mock_onboarding, mock_email, mock_settings, mock_storage,
        tmp_path,
    ) -> None:
        """init rejects invalid email format."""
        import os

        subprocess.run(  # noqa: S603
            ["git", "init", str(tmp_path)],  # noqa: S607
            capture_output=True,
            shell=False,
            timeout=10,
        )
        os.chdir(tmp_path)

        mock_email.return_value = None

        result = runner.invoke(
            app, ["init", "--email", "not-an-email"]
        )
        assert result.exit_code == 1
        assert "Invalid email" in result.output


# ── Tests: atrophy scan ────────────────────────────────────────────


class TestScan:
    """Tests for the scan command."""

    @patch("atrophy.cli.app._get_storage")
    def test_scan_no_project(self, mock_storage, tmp_path) -> None:
        """scan fails if no project is found."""
        import os

        os.chdir(tmp_path)

        storage_instance = AsyncMock()
        storage_instance.init_db = AsyncMock()
        storage_instance.get_project = AsyncMock(return_value=None)
        storage_instance.close = AsyncMock()
        mock_storage.return_value = storage_instance

        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 1
        assert "atrophy init" in result.output

    @patch("atrophy.config.get_settings")
    @patch("atrophy.cli.app._get_storage")
    @patch("atrophy.core.ai_detector.AIDetector")
    @patch("atrophy.core.git_scanner.GitScanner")
    @patch("atrophy.core.skill_mapper.SkillMapper")
    def test_scan_success(
        self, mock_mapper_cls, mock_scanner_cls,
        mock_detector_cls, mock_storage, mock_settings, tmp_path,
    ) -> None:
        """scan runs the full pipeline and prints summary."""
        import os

        os.chdir(tmp_path)

        project = _make_project(path=str(tmp_path))
        storage_instance = AsyncMock()
        storage_instance.init_db = AsyncMock()
        storage_instance.get_project = AsyncMock(return_value=project)
        storage_instance.upsert_commits = AsyncMock(return_value=10)
        storage_instance.save_skill_snapshots = AsyncMock()
        storage_instance.update_last_scanned = AsyncMock()
        storage_instance.set_setting = AsyncMock()
        storage_instance.get_all_skills_latest = AsyncMock(return_value=[])
        storage_instance.detect_and_save_wins = AsyncMock(return_value=[])
        storage_instance.get_setting = AsyncMock(return_value="0")
        storage_instance.close = AsyncMock()
        mock_storage.return_value = storage_instance

        # Mock scanner
        commits = _make_analyzed_commits(10)
        scanner_instance = MagicMock()
        scanner_instance.scan_commits.return_value = commits
        mock_scanner_cls.return_value = scanner_instance

        # Mock detector
        detector_instance = MagicMock()
        detector_instance.analyze_batch.return_value = commits
        detector_instance.get_summary_stats.return_value = {
            "total": 10,
            "human_count": 7,
            "ai_count": 3,
            "uncertain_count": 0,
            "human_ratio": 0.7,
            "avg_ai_probability": 0.3,
            "monthly_breakdown": {},
        }
        mock_detector_cls.return_value = detector_instance

        # Mock skill mapper
        mapper_instance = MagicMock()
        mapper_instance.map_skills.return_value = {
            "testing": {
                "score": 80,
                "last_seen": datetime.now(UTC),
                "total_hits": 20,
                "recent_hits": 5,
                "trend": "stable",
                "description": "Writing tests",
                "emoji": "✅",
            }
        }
        mapper_instance.get_dead_zones.return_value = []
        mapper_instance.get_strongest_skills.return_value = ["testing"]
        mapper_instance.get_coding_dna.return_value = {
            "primary_language": "py",
            "top_skills": ["testing"],
            "dead_zones": [],
            "ai_ratio": 0.3,
            "avg_commit_size": 15.0,
            "coding_style": "precise",
            "most_productive_hour": 14,
        }
        mock_mapper_cls.return_value = mapper_instance

        # Mock settings
        settings_instance = MagicMock()
        settings_instance.data_dir = tmp_path / ".atrophy"
        settings_instance.llm_provider = "none"
        mock_settings.return_value = settings_instance

        result = runner.invoke(app, ["scan"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Scan Complete" in result.output


# ── Tests: atrophy report ──────────────────────────────────────────


class TestReport:
    """Tests for the report command."""

    @patch("atrophy.cli.app._get_storage")
    def test_report_no_project(self, mock_storage, tmp_path) -> None:
        """report fails if no project is found."""
        import os

        os.chdir(tmp_path)

        storage_instance = AsyncMock()
        storage_instance.init_db = AsyncMock()
        storage_instance.get_project = AsyncMock(return_value=None)
        storage_instance.close = AsyncMock()
        mock_storage.return_value = storage_instance

        result = runner.invoke(app, ["report"])
        assert result.exit_code == 1
        assert "atrophy init" in result.output

    @patch("atrophy.cli.app._get_storage")
    def test_report_no_scan_data(self, mock_storage, tmp_path) -> None:
        """report fails if no scan data exists."""
        import os

        os.chdir(tmp_path)

        project = _make_project(path=str(tmp_path))
        storage_instance = AsyncMock()
        storage_instance.init_db = AsyncMock()
        storage_instance.get_project = AsyncMock(return_value=project)
        storage_instance.get_all_skills_latest = AsyncMock(
            return_value=[]
        )
        storage_instance.close = AsyncMock()
        mock_storage.return_value = storage_instance

        result = runner.invoke(app, ["report"])
        assert result.exit_code == 1
        assert "atrophy scan" in result.output

    @patch("atrophy.cli.app._get_storage")
    def test_report_json_output(self, mock_storage, tmp_path) -> None:
        """report --json outputs valid JSON."""
        import os

        os.chdir(tmp_path)

        project = _make_project(path=str(tmp_path))
        snapshots = [
            _make_skill_snapshot("testing", 80.0),
            _make_skill_snapshot("api_design", 45.0),
        ]
        coding_dna = {
            "primary_language": "py",
            "top_skills": ["testing"],
            "dead_zones": [],
            "ai_ratio": 0.25,
        }

        storage_instance = AsyncMock()
        storage_instance.init_db = AsyncMock()
        storage_instance.get_project = AsyncMock(return_value=project)
        storage_instance.get_all_skills_latest = AsyncMock(
            return_value=snapshots
        )
        storage_instance.get_setting = AsyncMock(
            side_effect=lambda k: (
                json.dumps(coding_dna) if k == "coding_dna" else None
            )
        )
        storage_instance.close = AsyncMock()
        mock_storage.return_value = storage_instance

        result = runner.invoke(app, ["report", "--json"])
        assert result.exit_code == 0
        # Should contain valid JSON with skills
        assert "testing" in result.output

    @patch("atrophy.cli.app._get_storage")
    def test_report_with_share(self, mock_storage, tmp_path) -> None:
        """report --share creates a report.md file."""
        import os

        os.chdir(tmp_path)

        project = _make_project(path=str(tmp_path))
        snapshots = [
            _make_skill_snapshot("testing", 80.0),
        ]
        coding_dna = {
            "primary_language": "py",
            "top_skills": ["testing"],
            "dead_zones": [],
            "ai_ratio": 0.2,
        }

        storage_instance = AsyncMock()
        storage_instance.init_db = AsyncMock()
        storage_instance.get_project = AsyncMock(return_value=project)
        storage_instance.get_all_skills_latest = AsyncMock(
            return_value=snapshots
        )
        storage_instance.get_setting = AsyncMock(
            side_effect=lambda k: (
                json.dumps(coding_dna) if k == "coding_dna" else None
            )
        )
        storage_instance.close = AsyncMock()
        mock_storage.return_value = storage_instance

        result = runner.invoke(app, ["report", "--share"])
        assert result.exit_code == 0
        report_path = tmp_path / "report.md"
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "# atrophy Skill Report" in content
        assert "testing" in content


# ── Tests: helper functions ─────────────────────────────────────────


class TestHelpers:
    """Tests for helper functions in app.py."""

    def test_validate_email_valid(self) -> None:
        """Valid emails are accepted."""
        from atrophy.cli.app import _validate_email

        assert _validate_email("user@example.com")
        assert _validate_email("foo.bar+test@domain.co.uk")

    def test_validate_email_invalid(self) -> None:
        """Invalid emails are rejected."""
        from atrophy.cli.app import _validate_email

        assert not _validate_email("not-an-email")
        assert not _validate_email("@missing-user.com")
        assert not _validate_email("user@")
        assert not _validate_email("")

    @patch("atrophy.cli.app.subprocess.run")
    def test_detect_email_success(self, mock_run) -> None:
        """Email is detected from git config."""
        from atrophy.cli.app import _detect_email

        mock_run.return_value = MagicMock(
            returncode=0, stdout="dev@example.com\n"
        )
        assert _detect_email() == "dev@example.com"

    @patch("atrophy.cli.app.subprocess.run")
    def test_detect_email_failure(self, mock_run) -> None:
        """Returns None when git config fails."""
        from atrophy.cli.app import _detect_email

        mock_run.return_value = MagicMock(
            returncode=1, stdout=""
        )
        assert _detect_email() is None

    @patch("atrophy.cli.app.subprocess.run")
    def test_detect_email_timeout(self, mock_run) -> None:
        """Returns None on timeout."""
        from atrophy.cli.app import _detect_email

        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="git", timeout=5
        )
        assert _detect_email() is None
