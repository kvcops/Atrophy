"""Async SQLite storage layer using SQLAlchemy 2.0.

Manages all persistence for atrophy: projects, commits, skill
snapshots, challenges, and settings. Uses async sessions exclusively.

Security:
    - All queries use SQLAlchemy ORM or parameterized statements.
    - Zero raw SQL string concatenation anywhere in this module.
    - User-supplied values always go through SQLAlchemy parameter binding.
"""

from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import (
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from atrophy.exceptions import AtrophyStorageError


# ── ORM Models ──────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base for all atrophy models."""


class Project(Base):
    """A tracked git repository."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    last_scanned_at: Mapped[datetime | None] = mapped_column(nullable=True)
    author_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

class Baseline(Base):
    """A developer's personal baseline metrics."""

    __tablename__ = "baselines"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), unique=True, index=True
    )
    avg_velocity: Mapped[float]
    uses_conventional_commits: Mapped[bool]
    uses_autoformatter: Mapped[bool]
    avg_commit_size: Mapped[float]
    computed_at: Mapped[datetime] = mapped_column(default=func.now())

class Commit(Base):
    """A single git commit with AI detection scores."""

    __tablename__ = "commits"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    commit_hash: Mapped[str] = mapped_column(
        String(40), unique=True, index=True
    )
    timestamp: Mapped[datetime]
    message: Mapped[str] = mapped_column(Text)
    additions: Mapped[int] = mapped_column(default=0)
    deletions: Mapped[int] = mapped_column(default=0)
    session_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ai_probability: Mapped[float] = mapped_column(default=0.5)
    classification: Mapped[str] = mapped_column(
        String(20), default="uncertain"
    )
    velocity_score: Mapped[float] = mapped_column(default=0.5)
    burstiness_score: Mapped[float] = mapped_column(default=0.5)
    formatting_score: Mapped[float] = mapped_column(default=0.5)
    message_score: Mapped[float] = mapped_column(default=0.5)
    entropy_score: Mapped[float] = mapped_column(default=0.5)


class SkillSnapshot(Base):
    """A point-in-time snapshot of a single skill score."""

    __tablename__ = "skill_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    snapshot_date: Mapped[date]
    skill_name: Mapped[str] = mapped_column(String(50))
    score: Mapped[float]
    last_seen: Mapped[datetime | None] = mapped_column(nullable=True)
    total_hits: Mapped[int] = mapped_column(default=0)

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "snapshot_date",
            "skill_name",
            name="uq_skill_snapshot",
        ),
    )


class Challenge(Base):
    """A generated coding challenge targeting a decaying skill."""

    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    skill_name: Mapped[str] = mapped_column(String(50))
    difficulty: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    completed: Mapped[bool] = mapped_column(default=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

class Win(Base):
    __tablename__ = "wins"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    date: Mapped[date]
    win_type: Mapped[str]   # "skill_improved", "dead_zone_cleared", "challenge_done", "streak_milestone", "new_skill_detected"
    skill_name: Mapped[str | None]
    message: Mapped[str]    # human-readable celebration


class Setting(Base):
    """A key-value pair for user preferences."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


# ── Storage Class ───────────────────────────────────────────────────


class Storage:
    """Async database access layer for atrophy.

    Uses SQLAlchemy 2.0 async engine and sessions. All public methods
    wrap database errors in AtrophyStorageError.

    Usage::

        storage = Storage(db_path)
        await storage.init_db()
        project = await storage.save_project("/path/to/repo", "my-repo")
    """

    def __init__(self, db_path: Path | str) -> None:
        """Initialize storage with a database path.

        Args:
            db_path: Path to the SQLite database file, or a full
                connection string like ``sqlite+aiosqlite:///:memory:``.
        """
        db_str = str(db_path)
        if db_str.startswith("sqlite"):
            # Already a connection string (e.g. for tests)
            url = db_str
        else:
            url = f"sqlite+aiosqlite:///{db_str}"

        self._engine = create_async_engine(url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    async def init_db(self) -> None:
        """Create all tables if they don't exist.

        Raises:
            AtrophyStorageError: If table creation fails.
        """
        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception as exc:
            msg = f"Failed to initialize database: {exc}"
            raise AtrophyStorageError(msg) from exc

    async def close(self) -> None:
        """Dispose of the engine and release all connections."""
        await self._engine.dispose()

    # ── Project operations ──────────────────────────────────────────

    async def save_project(
        self,
        path: str,
        name: str,
        author_email: str | None = None,
    ) -> Project:
        """Create or update a project record.

        If a project with the given path already exists, updates its
        name and author_email. Otherwise creates a new row.

        Args:
            path: Absolute path to the git repository.
            name: Human-readable project name.
            author_email: Optional author email filter.

        Returns:
            The saved Project instance.

        Raises:
            AtrophyStorageError: If the database operation fails.
        """
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Project).where(Project.path == path)
                    )
                    project = result.scalar_one_or_none()

                    if project is None:
                        project = Project(
                            name=name,
                            path=path,
                            author_email=author_email,
                        )
                        session.add(project)
                    else:
                        project.name = name
                        project.author_email = author_email

            return project
        except AtrophyStorageError:
            raise
        except Exception as exc:
            msg = f"Failed to save project '{name}': {exc}"
            raise AtrophyStorageError(msg) from exc

    async def get_project(self, path: str) -> Project | None:
        """Look up a project by its filesystem path.

        Args:
            path: Absolute path to the git repository.

        Returns:
            The Project if found, otherwise None.

        Raises:
            AtrophyStorageError: If the database query fails.
        """
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Project).where(Project.path == path)
                )
                return result.scalar_one_or_none()
        except Exception as exc:
            msg = f"Failed to look up project at '{path}': {exc}"
            raise AtrophyStorageError(msg) from exc

    async def update_last_scanned(self, project_id: int) -> None:
        """Set last_scanned_at to now for the given project.

        Args:
            project_id: Primary key of the project row.

        Raises:
            AtrophyStorageError: If the update fails.
        """
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Project).where(Project.id == project_id)
                    )
                    project = result.scalar_one_or_none()
                    if project is None:
                        msg = f"Project with id {project_id} not found"
                        raise AtrophyStorageError(msg)
                    project.last_scanned_at = datetime.now(timezone.utc)
        except AtrophyStorageError:
            raise
        except Exception as exc:
            msg = f"Failed to update last_scanned for project {project_id}: {exc}"
            raise AtrophyStorageError(msg) from exc

    async def save_baseline(self, project_id: int, baseline_data: dict) -> None:
        """Create or update a baseline record for the project."""
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Baseline).where(Baseline.project_id == project_id)
                    )
                    existing = result.scalar_one_or_none()

                    if existing is None:
                        baseline = Baseline(
                            project_id=project_id,
                            avg_velocity=baseline_data["avg_velocity"],
                            uses_conventional_commits=baseline_data["uses_conventional_commits"],
                            uses_autoformatter=baseline_data["uses_autoformatter"],
                            avg_commit_size=baseline_data["avg_commit_size"],
                            computed_at=datetime.now(timezone.utc),
                        )
                        session.add(baseline)
                    else:
                        existing.avg_velocity = baseline_data["avg_velocity"]
                        existing.uses_conventional_commits = baseline_data["uses_conventional_commits"]
                        existing.uses_autoformatter = baseline_data["uses_autoformatter"]
                        existing.avg_commit_size = baseline_data["avg_commit_size"]
                        existing.computed_at = datetime.now(timezone.utc)
        except AtrophyStorageError:
            raise
        except Exception as exc:
            msg = f"Failed to save baseline: {exc}"
            raise AtrophyStorageError(msg) from exc

    async def get_baseline(self, project_id: int) -> Baseline | None:
        """Look up the baseline for a project."""
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Baseline).where(Baseline.project_id == project_id)
                )
                return result.scalar_one_or_none()
        except Exception as exc:
            msg = f"Failed to get baseline: {exc}"
            raise AtrophyStorageError(msg) from exc

    # ── Commit operations ───────────────────────────────────────────

    async def upsert_commits(
        self, project_id: int, commits: list[dict]
    ) -> int:
        """Insert or update commit records.

        Uses commit_hash as the upsert key. If a commit already exists,
        its AI scores are updated. Otherwise a new row is inserted.

        Args:
            project_id: FK to the project these commits belong to.
            commits: List of commit dicts matching the data contract.

        Returns:
            Number of commits inserted or updated.

        Raises:
            AtrophyStorageError: If the upsert fails.
        """
        if not commits:
            return 0

        count = 0
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    for commit_data in commits:
                        commit_hash = commit_data["commit_hash"]
                        result = await session.execute(
                            select(Commit).where(
                                Commit.commit_hash == commit_hash
                            )
                        )
                        existing = result.scalar_one_or_none()

                        if existing is None:
                            commit = Commit(
                                project_id=project_id,
                                commit_hash=commit_hash,
                                timestamp=commit_data["timestamp"],
                                message=commit_data.get("message", ""),
                                additions=commit_data.get("additions", 0),
                                deletions=commit_data.get("deletions", 0),
                                session_id=commit_data.get("session_id"),
                                ai_probability=commit_data.get(
                                    "ai_probability", 0.5
                                ),
                                classification=commit_data.get(
                                    "classification", "uncertain"
                                ),
                                velocity_score=commit_data.get(
                                    "velocity_score", 0.5
                                ),
                                burstiness_score=commit_data.get(
                                    "burstiness_score", 0.5
                                ),
                                formatting_score=commit_data.get(
                                    "formatting_score", 0.5
                                ),
                                message_score=commit_data.get(
                                    "message_score", 0.5
                                ),
                                entropy_score=commit_data.get(
                                    "entropy_score", 0.5
                                ),
                            )
                            session.add(commit)
                        else:
                            # Update AI scores and session_id on existing commit
                            existing.session_id = commit_data.get(
                                "session_id", existing.session_id
                            )
                            existing.ai_probability = commit_data.get(
                                "ai_probability", existing.ai_probability
                            )
                            existing.classification = commit_data.get(
                                "classification", existing.classification
                            )
                            existing.velocity_score = commit_data.get(
                                "velocity_score", existing.velocity_score
                            )
                            existing.burstiness_score = commit_data.get(
                                "burstiness_score", existing.burstiness_score
                            )
                            existing.formatting_score = commit_data.get(
                                "formatting_score", existing.formatting_score
                            )
                            existing.message_score = commit_data.get(
                                "message_score", existing.message_score
                            )
                            existing.entropy_score = commit_data.get(
                                "entropy_score", existing.entropy_score
                            )

                        count += 1

            return count
        except AtrophyStorageError:
            raise
        except Exception as exc:
            msg = f"Failed to upsert commits: {exc}"
            raise AtrophyStorageError(msg) from exc

    # ── Skill snapshot operations ───────────────────────────────────

    async def save_skill_snapshots(
        self, project_id: int, skill_profile: dict
    ) -> None:
        """Save today's skill profile as a set of snapshot rows.

        Overwrites any existing entries for the same project + date +
        skill combination (using the unique constraint).

        Args:
            project_id: FK to the project.
            skill_profile: Dict mapping skill_name to a dict with
                keys: score, last_seen, total_hits (at minimum).

        Raises:
            AtrophyStorageError: If saving fails.
        """
        today = date.today()
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    for skill_name, skill_data in skill_profile.items():
                        # Check for existing snapshot
                        result = await session.execute(
                            select(SkillSnapshot).where(
                                SkillSnapshot.project_id == project_id,
                                SkillSnapshot.snapshot_date == today,
                                SkillSnapshot.skill_name == skill_name,
                            )
                        )
                        existing = result.scalar_one_or_none()

                        if existing is None:
                            snapshot = SkillSnapshot(
                                project_id=project_id,
                                snapshot_date=today,
                                skill_name=skill_name,
                                score=skill_data["score"],
                                last_seen=skill_data.get("last_seen"),
                                total_hits=skill_data.get("total_hits", 0),
                            )
                            session.add(snapshot)
                        else:
                            existing.score = skill_data["score"]
                            existing.last_seen = skill_data.get("last_seen")
                            existing.total_hits = skill_data.get(
                                "total_hits", 0
                            )
        except AtrophyStorageError:
            raise
        except Exception as exc:
            msg = f"Failed to save skill snapshots: {exc}"
            raise AtrophyStorageError(msg) from exc

    async def get_skill_history(
        self,
        project_id: int,
        skill: str,
        months: int = 6,
    ) -> list[SkillSnapshot]:
        """Retrieve historical snapshots for a skill.

        Args:
            project_id: FK to the project.
            skill: Skill name to query (e.g. ``"async_concurrency"``).
            months: How many months of history to fetch.

        Returns:
            List of SkillSnapshot rows, ordered by date ascending.

        Raises:
            AtrophyStorageError: If the query fails.
        """
        cutoff = date.today() - timedelta(days=months * 30)
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(SkillSnapshot)
                    .where(
                        SkillSnapshot.project_id == project_id,
                        SkillSnapshot.skill_name == skill,
                        SkillSnapshot.snapshot_date >= cutoff,
                    )
                    .order_by(SkillSnapshot.snapshot_date.asc())
                )
                return list(result.scalars().all())
        except Exception as exc:
            msg = f"Failed to get skill history for '{skill}': {exc}"
            raise AtrophyStorageError(msg) from exc

    async def get_all_skills_latest(
        self, project_id: int
    ) -> list[SkillSnapshot]:
        """Get the most recent snapshot for every skill.

        Uses a subquery to find the max snapshot_date per skill, then
        fetches the full rows.

        Args:
            project_id: FK to the project.

        Returns:
            List of the latest SkillSnapshot for each skill_name.

        Raises:
            AtrophyStorageError: If the query fails.
        """
        try:
            async with self._session_factory() as session:
                # Subquery: max date per skill for this project
                max_date_subq = (
                    select(
                        SkillSnapshot.skill_name,
                        func.max(SkillSnapshot.snapshot_date).label(
                            "max_date"
                        ),
                    )
                    .where(SkillSnapshot.project_id == project_id)
                    .group_by(SkillSnapshot.skill_name)
                    .subquery()
                )

                result = await session.execute(
                    select(SkillSnapshot)
                    .join(
                        max_date_subq,
                        (
                            SkillSnapshot.skill_name
                            == max_date_subq.c.skill_name
                        )
                        & (
                            SkillSnapshot.snapshot_date
                            == max_date_subq.c.max_date
                        ),
                    )
                    .where(SkillSnapshot.project_id == project_id)
                )
                return list(result.scalars().all())
        except Exception as exc:
            msg = f"Failed to get latest skills for project {project_id}: {exc}"
            raise AtrophyStorageError(msg) from exc

    # ── Challenge operations ────────────────────────────────────────

    async def save_challenges(
        self, project_id: int, challenges: list[dict]
    ) -> None:
        """Persist a batch of generated challenges.

        Args:
            project_id: FK to the project.
            challenges: List of challenge dicts matching the data contract.

        Raises:
            AtrophyStorageError: If saving fails.
        """
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    for ch in challenges:
                        challenge = Challenge(
                            project_id=project_id,
                            skill_name=ch["skill_name"],
                            difficulty=ch["difficulty"],
                            title=ch["title"],
                            description=ch["description"],
                            completed=False,
                        )
                        session.add(challenge)
        except AtrophyStorageError:
            raise
        except Exception as exc:
            msg = f"Failed to save challenges: {exc}"
            raise AtrophyStorageError(msg) from exc

    async def get_pending_challenges(
        self, project_id: int
    ) -> list[Challenge]:
        """Fetch all incomplete challenges for a project.

        Args:
            project_id: FK to the project.

        Returns:
            List of Challenge rows where completed is False,
            ordered by creation date descending (newest first).

        Raises:
            AtrophyStorageError: If the query fails.
        """
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Challenge)
                    .where(
                        Challenge.project_id == project_id,
                        Challenge.completed.is_(False),
                    )
                    .order_by(Challenge.created_at.desc())
                )
                return list(result.scalars().all())
        except Exception as exc:
            msg = f"Failed to get pending challenges: {exc}"
            raise AtrophyStorageError(msg) from exc

    async def mark_challenge_complete(self, challenge_id: int) -> None:
        """Mark a challenge as completed.

        Args:
            challenge_id: Primary key of the challenge row.

        Raises:
            AtrophyStorageError: If the challenge doesn't exist or
                the update fails.
        """
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Challenge).where(Challenge.id == challenge_id)
                    )
                    challenge = result.scalar_one_or_none()
                    if challenge is None:
                        msg = f"Challenge with id {challenge_id} not found"
                        raise AtrophyStorageError(msg)
                    challenge.completed = True
                    challenge.completed_at = datetime.now(timezone.utc)
        except AtrophyStorageError:
            raise
        except Exception as exc:
            msg = f"Failed to mark challenge {challenge_id} complete: {exc}"
            raise AtrophyStorageError(msg) from exc

    async def get_latest_challenge_date(
        self, project_id: int
    ) -> datetime | None:
        """Get the creation date of the most recent challenge.

        Args:
            project_id: FK to the project.

        Returns:
            The datetime of the latest challenge, or None if no challenges.

        Raises:
            AtrophyStorageError: If the query fails.
        """
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(func.max(Challenge.created_at)).where(
                        Challenge.project_id == project_id
                    )
                )
                return result.scalar_one_or_none()
        except Exception as exc:
            msg = f"Failed to get latest challenge date: {exc}"
            raise AtrophyStorageError(msg) from exc

    async def get_streak(self, project_id: int) -> int:
        """Calculate consecutive weeks a challenge was completed.

        Looks at 7-day windows starting from today going backward.
        Counts how many consecutive windows have at least one completion.
        If the current 7-day window has no completions, it checks if the
        *previous* window did to allow for a current-week grace period.

        Args:
            project_id: FK to the project.

        Returns:
            The streak count in weeks.

        Raises:
            AtrophyStorageError: If the query fails.
        """
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Challenge.completed_at)
                    .where(
                        Challenge.project_id == project_id,
                        Challenge.completed.is_(True),
                        Challenge.completed_at.is_not(None),
                    )
                    .order_by(Challenge.completed_at.desc())
                )
                completed_dates = list(result.scalars().all())

            if not completed_dates:
                return 0

            # Ensure all tz-naive dts are treated as UTC
            dates_utc = [
                d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d
                for d in completed_dates
            ]

            now = datetime.now(timezone.utc)
            streak = 0
            
            current_end = now
            current_start = now - timedelta(days=7)
            
            # Check the most recent 7-day window
            found_current = any(
                current_start <= d <= current_end for d in dates_utc
            )
            
            if found_current:
                streak += 1
                current_end = current_start
                current_start -= timedelta(days=7)
            else:
                # Give a grace period: skip the current incomplete week
                # and check if the previous week had a completion
                current_end = current_start
                current_start -= timedelta(days=7)
                found_prev = any(
                    current_start <= d <= current_end for d in dates_utc
                )
                if not found_prev:
                    return 0
                streak += 1
                current_end = current_start
                current_start -= timedelta(days=7)

            # Keep going backward
            while True:
                found_in_window = any(
                    current_start <= d <= current_end for d in dates_utc
                )
                if found_in_window:
                    streak += 1
                    current_end = current_start
                    current_start -= timedelta(days=7)
                else:
                    break

            return streak

        except Exception as exc:
            msg = f"Failed to calculate streak: {exc}"
            raise AtrophyStorageError(msg) from exc

    # ── Settings key-value store ────────────────────────────────────

    async def get_setting(
        self, key: str, default: str | None = None
    ) -> str | None:
        """Retrieve a setting value by key.

        Args:
            key: The setting key.
            default: Value to return if the key doesn't exist.

        Returns:
            The setting value, or default if not found.

        Raises:
            AtrophyStorageError: If the query fails.
        """
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(Setting).where(Setting.key == key)
                )
                setting = result.scalar_one_or_none()
                return setting.value if setting is not None else default
        except Exception as exc:
            msg = f"Failed to get setting '{key}': {exc}"
            raise AtrophyStorageError(msg) from exc

    async def set_setting(self, key: str, value: str) -> None:
        """Create or update a setting.

        Args:
            key: The setting key.
            value: The setting value.

        Raises:
            AtrophyStorageError: If the operation fails.
        """
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Setting).where(Setting.key == key)
                    )
                    setting = result.scalar_one_or_none()
                    if setting is None:
                        setting = Setting(key=key, value=value)
                        session.add(setting)
                    else:
                        setting.value = value
        except AtrophyStorageError:
            raise
        except Exception as exc:
            msg = f"Failed to set setting '{key}': {exc}"
            raise AtrophyStorageError(msg) from exc

    # ── Wins ────────────────────────────────────────────────────────

    async def detect_and_save_wins(
        self, project_id: int, old_profile: dict, new_profile: dict
    ) -> list[Win]:
        from atrophy.core.skill_mapper import SkillMapper
        wins = []
        old_dz = []
        mapper = SkillMapper()
        if old_profile:
            old_dz = mapper.get_dead_zones(old_profile)
        
        new_dz = mapper.get_dead_zones(new_profile)

        for skill, new_data in new_profile.items():
            old_data = old_profile.get(skill) if old_profile else {}
            
            # Use 0.0 if not present
            old_score = old_data.get("score", 0.0) if isinstance(old_data, dict) else 0.0
            new_score = new_data.get("score", 0.0) if isinstance(new_data, dict) else 0.0
            
            if old_score == 0.0 and new_score > 0.0 and old_profile:
                # new skill detected only if we had an old profile (otherwise it's the very first scan and everything is "new")
                wins.append(
                    Win(
                        project_id=project_id, date=date.today(),
                        win_type="new_skill_detected", skill_name=skill,
                        message=f"New skill detected: {skill}!"
                    )
                )
                continue

            diff = new_score - old_score
            if diff > 10:
                wins.append(
                    Win(
                        project_id=project_id, date=date.today(),
                        win_type="skill_improved", skill_name=skill,
                        message=f"Your {skill} improved by +{int(diff)} points!"
                    )
                )
            
            if skill in old_dz and skill not in new_dz:
                wins.append(
                    Win(
                        project_id=project_id, date=date.today(),
                        win_type="dead_zone_cleared", skill_name=skill,
                        message=f"You revived {skill}!"
                    )
                )

        if not wins:
            return []

        try:
            async with self._session_factory() as session:
                async with session.begin():
                    for w in wins:
                        session.add(w)
            return wins
        except Exception as exc:
            msg = f"Failed to save wins: {exc}"
            raise AtrophyStorageError(msg) from exc
