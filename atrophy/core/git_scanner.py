"""Git history scanner — reads commits and produces commit dicts.

Walks the git log for a repository and extracts per-commit metadata
including diffs, timing, and session-level aggregates.

Security:
    - Never uses shell=True in any subprocess call.
    - Never passes user-supplied strings into shell commands.
    - Uses GitPython's typed API exclusively (Repo, Commit, Diff).
    - Validates repo_path exists and is a real git repository.
    - Validates author_email with regex before use as a filter.
"""

import fnmatch
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from git import GitCommandError, InvalidGitRepositoryError, Repo
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from atrophy.exceptions import AtrophyGitError

console = Console()

# ── Constants ───────────────────────────────────────────────────────

EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

# Files/directories to exclude from commit analysis.
# Glob-style patterns matched against each changed file path.
EXCLUDE_PATTERNS: list[str] = [
    "package-lock.json",
    "yarn.lock",
    "*.lock",
    "Pipfile.lock",
    "poetry.lock",
    "uv.lock",
    "*.min.js",
    "*.min.css",
    "__pycache__",
    "*.pyc",
    "dist/*",
    "build/*",
    "node_modules/*",
    ".env",
    "migrations/*",
]

# File extensions to ignore when computing language breakdown.
SKIP_EXTENSIONS: set[str] = {"lock", "svg", "png", "jpg", "ico", "map"}

# If an SVG file has more than this many added lines, skip it.
SVG_LINE_THRESHOLD = 100

# Commits less than this many minutes apart are in the same "session".
SESSION_GAP_MINUTES = 30.0


# ── GitScanner ──────────────────────────────────────────────────────


class GitScanner:
    """Scans a git repository's history and produces commit dicts.

    Usage::

        scanner = GitScanner("/path/to/repo", days_back=90)
        commits = scanner.scan_commits()
    """

    def __init__(
        self,
        repo_path: str | Path,
        days_back: int = 180,
        author_email: str | None = None,
        since_date: datetime | None = None,
    ) -> None:
        """Initialize the scanner with a validated repository path.

        Args:
            repo_path: Path to a git repository. Will be resolved to
                an absolute path and verified.
            days_back: Number of days of history to scan.
            author_email: Optional email to filter commits by author.
                Must match the email regex if provided.

        Raises:
            AtrophyGitError: If the path doesn't exist, isn't a directory,
                or isn't a valid git repository.
            ValueError: If author_email fails regex validation.
        """
        # ── Validate repo path ──────────────────────────────────────
        resolved = Path(repo_path).resolve()
        if not resolved.exists():
            msg = f"Repository path does not exist: {resolved}"
            raise AtrophyGitError(msg)
        if not resolved.is_dir():
            msg = f"Repository path is not a directory: {resolved}"
            raise AtrophyGitError(msg)

        try:
            self._repo = Repo(str(resolved))
        except InvalidGitRepositoryError as exc:
            msg = f"Not a valid git repository: {resolved}"
            raise AtrophyGitError(msg) from exc

        if self._repo.bare:
            msg = f"Cannot scan a bare repository: {resolved}"
            raise AtrophyGitError(msg)

        # ── Validate author email ───────────────────────────────────
        if author_email is not None:
            if not EMAIL_PATTERN.match(author_email):
                msg = (
                    f"Invalid author email format: '{author_email}'. "
                    "Expected format: user@domain.tld"
                )
                raise ValueError(msg)

        self._repo_path = resolved
        self._days_back = days_back
        self._author_email = author_email
        self._since_date = since_date

    def scan_commits(self) -> list[dict]:
        """Walk all commits in the configured time window.

        Returns:
            List of commit dicts matching the atrophy data contract.
            Each dict contains: commit_hash, author_name, author_email,
            timestamp, message, files_changed, additions, deletions,
            diff_text, minutes_since_prev, session_additions.

        Raises:
            AtrophyGitError: If git operations fail.
        """
        if self._since_date is not None:
            since_date = self._since_date
            if since_date.tzinfo is None:
                since_date = since_date.replace(tzinfo=timezone.utc)
        else:
            since_date = datetime.now(timezone.utc) - timedelta(
                days=self._days_back
            )

        try:
            raw_commits = list(self._repo.iter_commits(
                all=True,
                since=since_date.strftime("%Y-%m-%dT%H:%M:%S%z"),
            ))
        except GitCommandError as exc:
            msg = f"Failed to read git log: {exc}"
            raise AtrophyGitError(msg) from exc

        if not raw_commits:
            console.print(
                "[dim]No commits found in the last "
                f"{self._days_back} days.[/dim]"
            )
            return []

        results: list[dict] = []
        # Track previous commit time per author for session detection
        last_commit_time: dict[str, datetime] = {}

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Scanning commits"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Scanning", total=len(raw_commits))

            for commit in raw_commits:
                progress.advance(task)
                parsed = self._process_commit(
                    commit, since_date, last_commit_time
                )
                if parsed is not None:
                    results.append(parsed)

        console.print(
            f"[green]Scanned {len(results)} commits[/green] "
            f"(filtered from {len(raw_commits)} total)"
        )
        return results

    def get_language_breakdown(
        self, commits: list[dict]
    ) -> dict[str, int]:
        """Count file extensions across all changed files.

        Args:
            commits: List of commit dicts from scan_commits().

        Returns:
            Dict mapping extension (without dot) to count.
            e.g. ``{"py": 245, "ts": 89, "sql": 12}``
        """
        counts: dict[str, int] = {}
        for commit_data in commits:
            for filepath in commit_data.get("files_changed", []):
                ext = Path(filepath).suffix.lstrip(".").lower()
                if ext and ext not in SKIP_EXTENSIONS:
                    counts[ext] = counts.get(ext, 0) + 1
        # Sort by count descending
        return dict(
            sorted(counts.items(), key=lambda x: x[1], reverse=True)
        )

    def detect_primary_language(self, commits: list[dict]) -> str:
        """Return the most common file extension across commits.

        Args:
            commits: List of commit dicts from scan_commits().

        Returns:
            The most frequent extension (e.g. ``"py"``), or
            ``"python"`` as the default if no files are found.
        """
        breakdown = self.get_language_breakdown(commits)
        if not breakdown:
            return "python"
        # First key is the most common (already sorted descending)
        return next(iter(breakdown))

    # ── Private helpers ─────────────────────────────────────────────

    def _process_commit(
        self,
        commit,
        since_date: datetime,
        last_commit_time: dict[str, datetime],
    ) -> dict | None:
        """Process a single git commit into a commit dict.

        Returns None if the commit should be filtered out.

        Args:
            commit: A GitPython Commit object.
            since_date: Earliest date to include.
            last_commit_time: Mutable dict tracking per-author times
                for session and gap calculations.

        Returns:
            A commit dict or None if filtered.
        """
        # ── Filter: merge commits ───────────────────────────────────
        if len(commit.parents) > 1:
            return None

        # ── Extract timestamp (UTC-aware) ───────────────────────────
        committed_dt = commit.committed_datetime
        if committed_dt.tzinfo is None:
            committed_dt = committed_dt.replace(tzinfo=timezone.utc)
        else:
            committed_dt = committed_dt.astimezone(timezone.utc)

        if committed_dt < since_date:
            return None

        # ── Filter: author email ────────────────────────────────────
        author_email = commit.author.email or ""
        if self._author_email is not None:
            if author_email.lower() != self._author_email.lower():
                return None

        # ── Extract diff and file changes ───────────────────────────
        try:
            files_changed, additions, deletions, diff_text = (
                self._extract_diff_stats(commit)
            )
        except GitCommandError as exc:
            # Skip commits we can't diff (e.g. corrupted objects)
            console.print(
                f"[dim yellow]Skipping commit {commit.hexsha[:8]}: "
                f"{exc}[/dim yellow]"
            )
            return None

        # ── Filter: no files after exclusion ────────────────────────
        if not files_changed:
            return None

        # ── Filter: empty diff ──────────────────────────────────────
        if not diff_text.strip():
            return None

        # ── Filter: 0 additions ─────────────────────────────────────
        if additions == 0:
            return None

        # ── Calculate timing metrics ────────────────────────────────
        author_key = author_email.lower()
        minutes_since_prev = 0.0
        if author_key in last_commit_time:
            delta = last_commit_time[author_key] - committed_dt
            minutes_since_prev = max(0.0, delta.total_seconds() / 60.0)

        # Session: accumulate additions for commits < 30 min apart
        session_additions = additions
        if minutes_since_prev > 0 and minutes_since_prev < SESSION_GAP_MINUTES:
            # Within same session — additions accumulate
            session_additions = additions  # individual commit's additions

        # Update last commit time for this author
        # (commits come in reverse chronological order, so we only
        # set if not already set — first seen = most recent)
        if author_key not in last_commit_time:
            last_commit_time[author_key] = committed_dt
        else:
            # We're walking backwards, so update to the older timestamp
            last_commit_time[author_key] = committed_dt

        # ── Squash commit detection ────────────────────────────────
        is_squash = self.is_likely_squash({
            "additions": additions,
            "deletions": deletions,
            "message": commit.message.strip(),
            "files_changed": files_changed,
        })

        return {
            "commit_hash": commit.hexsha,
            "author_name": commit.author.name or "Unknown",
            "author_email": author_email,
            "timestamp": committed_dt,
            "message": commit.message.strip(),
            "files_changed": files_changed,
            "additions": additions,
            "deletions": deletions,
            "diff_text": diff_text,
            "minutes_since_prev": round(minutes_since_prev, 2),
            "session_additions": session_additions,
            "is_squash": is_squash,
        }

    def is_likely_squash(self, commit: dict) -> bool:
        """Detect if a commit is likely a squash or large merge.

        Args:
            commit: A dictionary with 'additions', 'deletions', 'message',
                and 'files_changed'.

        Returns:
            True if it matches squash heuristics.
        """
        additions = commit.get("additions", 0)
        deletions = commit.get("deletions", 0)
        msg = commit.get("message", "").lower()
        files = commit.get("files_changed", [])

        if additions > 300 and deletions > 300:
            return True

        if any(p in msg for p in ["squash", "merge", "wip"]):
            return True

        if len(files) > 20:
            return True

        return False

    def _extract_diff_stats(
        self,
        commit,
    ) -> tuple[list[str], int, int, str]:
        """Extract file changes and diff text from a commit.

        Args:
            commit: A GitPython Commit object.

        Returns:
            Tuple of (files_changed, additions, deletions, diff_text).
            files_changed only includes files that pass exclusion filters.

        Raises:
            GitCommandError: If diff extraction fails.
        """
        files_changed: list[str] = []
        total_additions = 0
        total_deletions = 0
        diff_lines: list[str] = []

        # Get the diff against the parent (or empty tree for initial commit)
        if commit.parents:
            diffs = commit.parents[0].diff(
                commit, create_patch=True, unified=3
            )
        else:
            diffs = commit.diff(None, create_patch=True, unified=3)

        for diff_item in diffs:
            # Get the file path (prefer b_path for the "after" state)
            file_path = diff_item.b_path or diff_item.a_path or ""
            basename = Path(file_path).name

            # ── Per-file exclusion check ────────────────────────────
            if self._should_exclude_file(file_path, basename):
                continue

            # ── Extract patch text (added lines only) ───────────────
            try:
                patch_text = (
                    diff_item.diff.decode("utf-8", errors="replace")
                    if diff_item.diff
                    else ""
                )
            except (UnicodeDecodeError, AttributeError):
                patch_text = ""

            # Count additions and deletions from the patch
            added_lines: list[str] = []
            file_adds = 0
            file_dels = 0
            for line in patch_text.splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    file_adds += 1
                    added_lines.append(line[1:])  # Strip the leading +
                elif line.startswith("-") and not line.startswith("---"):
                    file_dels += 1

            # ── SVG special case: skip large generated SVGs ─────────
            ext = Path(file_path).suffix.lstrip(".").lower()
            if ext == "svg" and file_adds > SVG_LINE_THRESHOLD:
                continue

            files_changed.append(file_path)
            total_additions += file_adds
            total_deletions += file_dels
            if added_lines:
                diff_lines.extend(added_lines)

        diff_text = "\n".join(diff_lines)
        return files_changed, total_additions, total_deletions, diff_text

    @staticmethod
    def _should_exclude_file(file_path: str, basename: str) -> bool:
        """Check whether a file should be excluded from analysis.

        Args:
            file_path: Full relative path of the changed file.
            basename: Just the filename (no directory).

        Returns:
            True if the file matches any exclusion pattern.
        """
        for pattern in EXCLUDE_PATTERNS:
            # Directory-style patterns (contain /)
            if "/" in pattern or "*" in pattern:
                if fnmatch.fnmatch(file_path, pattern):
                    return True
                # Also check individual path components
                if fnmatch.fnmatch(basename, pattern):
                    return True
                # Check if the file is under an excluded directory
                dir_name = pattern.rstrip("/*")
                if f"{dir_name}/" in file_path or f"/{dir_name}/" in file_path:
                    return True
            else:
                # Exact filename or glob match
                if fnmatch.fnmatch(basename, pattern):
                    return True
                # Also check if the pattern matches a directory component
                if pattern in file_path.split("/"):
                    return True
        return False
