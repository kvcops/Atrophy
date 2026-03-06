"""Skill mapper — categorizes human commits into 10 coding skill areas.

Maps commit diffs to skill categories using a 3-layer detection system:
    Layer 1: tree-sitter AST analysis (most accurate, for supported languages)
    Layer 2: LLM-based classification (for unsupported languages / complex diffs)
    Layer 3: Keyword pattern fallback (legacy, always available)

Only processes commits classified as human-leaning (ai_probability < 0.55).

The 10 canonical skill categories are:
    async_concurrency, data_structures, sql_databases, regex_parsing,
    error_handling, api_design, testing, algorithms, system_io, security
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Skill Patterns ──────────────────────────────────────────────────

SKILL_PATTERNS: dict[str, dict] = {
    "async_concurrency": {
        "keywords": [
            "async def ",
            "await ",
            "asyncio.",
            "Promise.",
            "setTimeout",
            "threading.",
            "multiprocessing.",
            "concurrent.",
            "goroutine",
            "tokio::",
            "Future<",
            ".await",
            "spawn(",
            "select!",
        ],
        "file_extensions": ["py", "rs", "go", "ts", "js"],
        "description": "Async programming, concurrency, parallel processing",
        "emoji": "⚡",
    },
    "data_structures": {
        "keywords": [
            "class ",
            "def __init__",
            "LinkedList",
            "BinaryTree",
            "heap",
            "deque",
            "defaultdict",
            "OrderedDict",
            "@dataclass",
            "struct ",
            "impl ",
            "interface ",
            "HashMap",
        ],
        "file_extensions": ["py", "rs", "go", "ts", "java"],
        "description": "Custom data structures, OOP, type design",
        "emoji": "🏗️",
    },
    "sql_databases": {
        "keywords": [
            "SELECT ",
            "INSERT INTO",
            "UPDATE ",
            "DELETE FROM",
            "JOIN ",
            "WHERE ",
            "cursor.execute",
            "session.query",
            "db.query",
            ".raw(",
            "execute(",
            "fetchall",
            "fetchone",
            "GROUP BY",
            "ORDER BY",
        ],
        "file_extensions": ["py", "sql", "ts", "go"],
        "description": "SQL queries, ORM usage, database design",
        "emoji": "🗄️",
    },
    "regex_parsing": {
        "keywords": [
            "re.compile",
            "re.match",
            "re.search",
            "re.sub",
            "RegExp(",
            ".match(/",
            ".replace(/",
            "pattern=",
            "re.findall",
            "re.fullmatch",
            "Regex::new",
        ],
        "file_extensions": ["py", "ts", "js", "rs", "go"],
        "description": "Regular expressions, string parsing",
        "emoji": "🔍",
    },
    "error_handling": {
        "keywords": [
            "try:",
            "except ",
            "catch (",
            "catch {",
            "raise ",
            "throw new",
            "throw ",
            "finally:",
            "Result<",
            "Option<",
            "Err(",
            "unwrap_or",
            "logger.error",
            "traceback",
            "CustomError",
            "class.*Exception",
            "class.*Error",
        ],
        "file_extensions": ["py", "ts", "js", "rs", "go"],
        "description": "Exception handling, error recovery, logging",
        "emoji": "🛡️",
    },
    "api_design": {
        "keywords": [
            "@app.route",
            "@router.",
            "app.get(",
            "app.post(",
            "app.put(",
            "app.delete(",
            "@Controller",
            "middleware",
            "@decorator",
            "Handler",
            "endpoint",
            "@Get(",
            "@Post(",
        ],
        "file_extensions": ["py", "ts", "go"],
        "description": "API routes, middleware, endpoint design",
        "emoji": "🌐",
    },
    "testing": {
        "keywords": [
            "def test_",
            "it(",
            "describe(",
            "assert ",
            "expect(",
            "mock.",
            "@patch",
            "fixture",
            "pytest.",
            "beforeEach",
            "afterAll",
            "test(",
            "spec(",
            "#[test]",
            "t.Run(",
        ],
        "file_extensions": ["py", "ts", "js", "rs", "go"],
        "description": "Writing tests, assertions, mocking",
        "emoji": "✅",
    },
    "algorithms": {
        "keywords": [
            "def sort",
            "binary_search",
            "def recursion",
            "fibonacci",
            "memoize",
            "cache",
            "O(n",
            "dynamic_programming",
            "def dfs",
            "def bfs",
            "heapq.",
            "bisect.",
            "reduce(",
            "fn factorial",
            "func sort",
        ],
        "file_extensions": ["py", "ts", "rs", "go", "cpp"],
        "description": "Algorithms, recursion, optimization",
        "emoji": "🧮",
    },
    "system_io": {
        "keywords": [
            "open(",
            "os.path",
            "pathlib.",
            "subprocess.",
            "socket.",
            "readline(",
            ".write(",
            "fs.readFile",
            "fs.writeFile",
            "std::fs",
            "os.Open",
            "io.Reader",
            "io.Writer",
        ],
        "file_extensions": ["py", "ts", "rs", "go"],
        "description": "File I/O, system calls, networking",
        "emoji": "💾",
    },
    "security": {
        "keywords": [
            "hash(",
            "bcrypt",
            "jwt",
            "token",
            "sanitize",
            "validate(",
            "escape(",
            "csrf",
            "authenticate",
            "authorize",
            "SecretStr",
            "getpass",
            "hmac",
            "secrets.",
            "Argon2",
            "permission_required",
        ],
        "file_extensions": ["py", "ts", "go"],
        "description": "Auth, input validation, crypto, permissions",
        "emoji": "🔒",
    },
}

# ── Recency weight boundaries ──────────────────────────────────────

RECENCY_WEIGHT_RECENT = 3.0  # last 30 days
RECENCY_WEIGHT_MID = 2.0  # 31–90 days
RECENCY_WEIGHT_OLD = 1.0  # older than 90 days

# AI probability threshold — only analyze human-leaning commits
AI_THRESHOLD = 0.55

# Minimum added lines to use tree-sitter analysis
MIN_AST_LINES = 10

# Minimum diff length to use LLM classification
MIN_LLM_CHARS = 100

# Comment patterns per language for the simple stripper
_COMMENT_PATTERNS: dict[str, re.Pattern] = {
    "py": re.compile(r"(#.*)|(\"\"\"[\s\S]*?\"\"\")|('''[\s\S]*?''')"),
    "ts": re.compile(r"(//.*)|(/\*[\s\S]*?\*/)"),
    "js": re.compile(r"(//.*)|(/\*[\s\S]*?\*/)"),
    "rs": re.compile(r"(//.*)|(/\*[\s\S]*?\*/)"),
    "go": re.compile(r"(//.*)|(/\*[\s\S]*?\*/)"),
    "java": re.compile(r"(//.*)|(/\*[\s\S]*?\*/)"),
    "rb": re.compile(r"(#.*)|(=begin[\s\S]*?=end)"),
    "cpp": re.compile(r"(//.*)|(/\*[\s\S]*?\*/)"),
    "c": re.compile(r"(//.*)|(/\*[\s\S]*?\*/)"),
}


# ── SkillMapper ─────────────────────────────────────────────────────


class SkillMapper:
    """Maps human commits to 10 canonical coding skill categories.

    Uses a 3-layer detection system:
        1. **tree-sitter AST** for supported languages (most accurate)
        2. **LLM classification** for unsupported languages (last 90 days)
        3. **Keyword fallback** for everything else

    Only processes commits where ``ai_probability < 0.55``. Applies
    recency weighting (3x for last 30 days, 2x for 31–90, 1x older)
    and normalizes scores to 0–100.
    """

    def __init__(
        self,
        tree_sitter_analyzer=None,
        llm_classifier=None,
    ) -> None:
        """Initialize with optional analyzer and classifier.

        Args:
            tree_sitter_analyzer: Optional TreeSitterAnalyzer instance.
                If None, one will be lazily created on first use.
            llm_classifier: Optional LLMSkillClassifier instance.
                If None, LLM classification is skipped.
        """
        self._ts_analyzer = tree_sitter_analyzer
        self._llm_classifier = llm_classifier
        self._ts_initialized = tree_sitter_analyzer is not None

        # Detection stats
        self.stats_ast: int = 0
        self.stats_llm: int = 0
        self.stats_keyword: int = 0

    def _get_ts_analyzer(self):
        """Lazy-load the tree-sitter analyzer.

        Returns:
            TreeSitterAnalyzer instance, or None if import fails.
        """
        if self._ts_initialized:
            return self._ts_analyzer

        self._ts_initialized = True
        try:
            from atrophy.core.tree_sitter_analyzer import (
                TreeSitterAnalyzer,
            )

            self._ts_analyzer = TreeSitterAnalyzer()
        except ImportError:
            logger.debug(
                "tree-sitter-language-pack not available; "
                "falling back to keyword detection",
            )
            self._ts_analyzer = None

        return self._ts_analyzer

    def map_skills(self, commits: list[dict]) -> dict[str, dict]:
        """Build a skill profile from analyzed commits.

        Uses the 3-layer detection system for each commit:
        1. tree-sitter AST (if language supported and diff >= 10 lines)
        2. LLM classifier (if provider available & diff >= 100 chars
           & commit in last 90 days)
        3. Keyword fallback (with comment stripping)

        Args:
            commits: List of commit dicts from AIDetector (must have
                ``ai_probability``, ``diff_text``, ``files_changed``,
                ``timestamp``, ``additions``).

        Returns:
            Dict mapping each of the 10 skill names to a skill data
            dict with: score, last_seen, total_hits, recent_hits,
            trend, description, emoji.
        """
        now = datetime.now(UTC)
        thirty_days_ago = now - timedelta(days=30)
        ninety_days_ago = now - timedelta(days=90)

        # Accumulators per skill
        weighted_hits: dict[str, float] = dict.fromkeys(SKILL_PATTERNS, 0.0)
        total_hits: dict[str, int] = dict.fromkeys(SKILL_PATTERNS, 0)
        recent_hits: dict[str, int] = dict.fromkeys(SKILL_PATTERNS, 0)
        last_seen: dict[str, datetime | None] = dict.fromkeys(SKILL_PATTERNS)
        # For trend: hits in month M-1 vs month M-2
        month_1_hits: dict[str, int] = dict.fromkeys(SKILL_PATTERNS, 0)
        month_2_hits: dict[str, int] = dict.fromkeys(SKILL_PATTERNS, 0)
        sixty_days_ago = now - timedelta(days=60)

        # Reset detection stats
        self.stats_ast = 0
        self.stats_llm = 0
        self.stats_keyword = 0

        # Get the tree-sitter analyzer
        ts = self._get_ts_analyzer()

        # Build keyword map for tree-sitter fallback
        fallback_keywords = {
            name: pattern["keywords"]
            for name, pattern in SKILL_PATTERNS.items()
        }

        # Filter to human-leaning commits only
        human_commits = [
            c
            for c in commits
            if c.get("ai_probability", 1.0) < AI_THRESHOLD
        ]

        for commit in human_commits:
            ts_val = commit.get("timestamp")
            if ts_val is None:
                continue

            # Ensure timezone-aware
            if ts_val.tzinfo is None:
                ts_val = ts_val.replace(tzinfo=UTC)

            # Determine recency weight
            if ts_val >= thirty_days_ago:
                weight = RECENCY_WEIGHT_RECENT
            elif ts_val >= ninety_days_ago:
                weight = RECENCY_WEIGHT_MID
            else:
                weight = RECENCY_WEIGHT_OLD

            # Determine which month bucket for trend
            is_month_1 = ts_val >= thirty_days_ago
            is_month_2 = (
                sixty_days_ago <= ts_val < thirty_days_ago
            )

            # Get file extensions from this commit
            commit_extensions = self._get_extensions(
                commit.get("files_changed", [])
            )
            diff_text = commit.get("diff_text", "")

            # Count added lines
            added_lines = sum(
                1
                for line in diff_text.splitlines()
                if line.startswith("+")
                and not line.startswith("+++")
            )

            # Determine primary extension for this commit
            primary_ext = self._primary_extension(
                commit.get("files_changed", [])
            )

            # ── Layer 1: tree-sitter AST ────────────────────
            skill_hits: dict[str, int] = {}
            detection_method = "keyword"

            if (
                ts is not None
                and primary_ext is not None
                and ts.is_supported(primary_ext)
                and added_lines >= MIN_AST_LINES
            ):
                skill_hits = ts.analyze_diff(
                    diff_text,
                    primary_ext,
                    keywords_by_skill=fallback_keywords,
                )
                if skill_hits:
                    detection_method = "ast"

            # ── Layer 2: LLM classification ─────────────────
            if (
                not skill_hits
                and self._llm_classifier is not None
                and len(diff_text) >= MIN_LLM_CHARS
                and ts_val >= ninety_days_ago
            ):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # We're inside an async context
                        import concurrent.futures

                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            llm_result = pool.submit(
                                asyncio.run,
                                self._llm_classifier.classify_diff(
                                    diff_text, primary_ext or "unknown",
                                ),
                            ).result()
                    else:
                        llm_result = asyncio.run(
                            self._llm_classifier.classify_diff(
                                diff_text,
                                primary_ext or "unknown",
                            )
                        )
                except Exception:
                    llm_result = {}

                if llm_result:
                    # Convert confidence scores to hit counts
                    # Score of 1.0 → 3 hits, 0.5 → 1 hit
                    skill_hits = {
                        name: max(1, int(score * 3))
                        for name, score in llm_result.items()
                    }
                    detection_method = "llm"

            # ── Layer 3: Keyword fallback ───────────────────
            if not skill_hits:
                # Use keyword scanning with comment stripping
                stripped_diff = self._strip_comments(
                    diff_text, primary_ext,
                )
                skill_hits = self._keyword_scan(
                    stripped_diff, commit_extensions,
                )
                detection_method = "keyword"

            # Track detection method
            if detection_method == "ast":
                self.stats_ast += 1
            elif detection_method == "llm":
                self.stats_llm += 1
            else:
                self.stats_keyword += 1

            # Apply hits to accumulators
            for skill_name, hits in skill_hits.items():
                if skill_name not in SKILL_PATTERNS:
                    continue
                if hits == 0:
                    continue

                total_hits[skill_name] += hits
                weighted_hits[skill_name] += hits * weight

                if ts_val >= thirty_days_ago:
                    recent_hits[skill_name] += hits

                if is_month_1:
                    month_1_hits[skill_name] += hits
                elif is_month_2:
                    month_2_hits[skill_name] += hits

                # Track most recent occurrence
                if (
                    last_seen[skill_name] is None
                    or ts_val > last_seen[skill_name]
                ):
                    last_seen[skill_name] = ts_val

        # Build the final profile
        profile: dict[str, dict] = {}
        for skill_name, pattern_def in SKILL_PATTERNS.items():
            score = min(
                100.0, weighted_hits[skill_name] * 2.5
            )
            trend = self._compute_trend(
                month_1_hits[skill_name],
                month_2_hits[skill_name],
                total_hits[skill_name],
            )

            profile[skill_name] = {
                "score": round(score, 1),
                "last_seen": last_seen[skill_name],
                "total_hits": total_hits[skill_name],
                "recent_hits": recent_hits[skill_name],
                "trend": trend,
                "description": pattern_def["description"],
                "emoji": pattern_def["emoji"],
            }

        return profile

    def get_detection_stats(self) -> dict[str, int]:
        """Return detection method statistics from the last scan.

        Returns:
            Dict with keys 'ast', 'llm', 'keyword' and
            their respective commit counts.
        """
        return {
            "ast": self.stats_ast,
            "llm": self.stats_llm,
            "keyword": self.stats_keyword,
        }

    def get_dead_zones(
        self, skill_profile: dict, threshold_days: int = 45
    ) -> list[str]:
        """Return skill names that are in the "dead zone".

        A skill is dead if:
        - ``last_seen`` is None (never exercised), OR
        - ``last_seen`` is more than ``threshold_days`` ago, OR
        - ``score < 8`` (barely exercised)

        Args:
            skill_profile: Output of ``map_skills()``.
            threshold_days: Number of days before a skill is "dead".

        Returns:
            List of skill names sorted by urgency (longest since
            last use first, then never-used skills at the end).
        """
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=threshold_days)
        dead: list[tuple[str, datetime | None]] = []

        for skill_name, data in skill_profile.items():
            ls = data.get("last_seen")
            score = data.get("score", 0.0)

            if ls is None or score < 8:
                dead.append((skill_name, ls))
            elif ls < cutoff:
                dead.append((skill_name, ls))

        # Sort: skills with a date come first (oldest first),
        # then skills with None (never used) at the end
        dead.sort(key=lambda x: (x[1] is None, x[1] or now))
        return [name for name, _ in dead]

    def get_strongest_skills(
        self, skill_profile: dict, top_n: int = 3
    ) -> list[str]:
        """Return the top N skills by score.

        Args:
            skill_profile: Output of ``map_skills()``.
            top_n: Number of top skills to return.

        Returns:
            List of skill names, highest score first.
        """
        sorted_skills = sorted(
            skill_profile.items(),
            key=lambda x: x[1]["score"],
            reverse=True,
        )
        return [name for name, _ in sorted_skills[:top_n]]

    def get_monthly_skill_scores(
        self,
        commits: list[dict],
        skill: str,
        months: int = 6,
    ) -> list[dict]:
        """Compute per-month scores for a single skill.

        Args:
            commits: Analyzed commits from AIDetector.
            skill: Skill name to compute scores for.
            months: Number of months to look back.

        Returns:
            List of ``{"month": "YYYY-MM", "score": float}`` dicts,
            one per month, newest last. Months with no human commits
            in the skill get score 0.
        """
        if skill not in SKILL_PATTERNS:
            return []

        now = datetime.now(UTC)
        pattern_def = SKILL_PATTERNS[skill]
        skill_exts = set(pattern_def["file_extensions"])

        # Build month buckets
        month_hits: dict[str, int] = {}
        for i in range(months):
            dt = now - timedelta(days=i * 30)
            key = dt.strftime("%Y-%m")
            month_hits[key] = 0

        human_commits = [
            c
            for c in commits
            if c.get("ai_probability", 1.0) < AI_THRESHOLD
        ]

        for commit in human_commits:
            ts_val = commit.get("timestamp")
            if ts_val is None:
                continue

            if ts_val.tzinfo is None:
                ts_val = ts_val.replace(tzinfo=UTC)

            month_key = ts_val.strftime("%Y-%m")
            if month_key not in month_hits:
                continue

            commit_exts = self._get_extensions(
                commit.get("files_changed", [])
            )
            if commit_exts and not commit_exts & skill_exts:
                continue

            hits = self._count_keyword_hits(
                commit.get("diff_text", ""),
                pattern_def["keywords"],
            )
            month_hits[month_key] += hits

        # Convert hits to scores and sort chronologically
        result: list[dict] = []
        for month_key in sorted(month_hits.keys()):
            score = min(
                100.0, month_hits[month_key] * 2.5,
            )
            result.append(
                {"month": month_key, "score": round(score, 1)}
            )

        return result

    def get_coding_dna(
        self, commits: list[dict], skill_profile: dict
    ) -> dict:
        """Build a unique "coding DNA" profile for the developer.

        Args:
            commits: Analyzed commits from AIDetector.
            skill_profile: Output of ``map_skills()``.

        Returns:
            Dict with: primary_language, top_skills, dead_zones,
            ai_ratio, avg_commit_size, coding_style,
            most_productive_hour.
        """
        # Primary language
        ext_counts: Counter[str] = Counter()
        for commit in commits:
            for fp in commit.get("files_changed", []):
                ext = Path(fp).suffix.lstrip(".").lower()
                if ext:
                    ext_counts[ext] += 1
        primary_language = (
            ext_counts.most_common(1)[0][0]
            if ext_counts
            else "python"
        )

        # AI ratio
        total = len(commits)
        ai_count = sum(
            1
            for c in commits
            if c.get("classification") == "ai"
        )
        ai_ratio = ai_count / total if total > 0 else 0.0

        # Average commit size
        additions = [c.get("additions", 0) for c in commits]
        avg_commit_size = (
            sum(additions) / len(additions) if additions else 0.0
        )

        # Most productive hour
        hour_counts: Counter[int] = Counter()
        for commit in commits:
            ts_val = commit.get("timestamp")
            if ts_val is not None:
                hour_counts[ts_val.hour] += 1
        most_productive_hour = (
            hour_counts.most_common(1)[0][0]
            if hour_counts
            else None
        )

        # Top skills and dead zones
        top_skills = self.get_strongest_skills(skill_profile)
        dead_zones = self.get_dead_zones(skill_profile)

        # Determine coding style
        coding_style = self._determine_style(
            ai_ratio, avg_commit_size,
        )

        return {
            "primary_language": primary_language,
            "top_skills": top_skills,
            "dead_zones": dead_zones,
            "ai_ratio": round(ai_ratio, 4),
            "avg_commit_size": round(avg_commit_size, 1),
            "coding_style": coding_style,
            "most_productive_hour": most_productive_hour,
        }

    # ── Private helpers ─────────────────────────────────────────────

    def _keyword_scan(
        self,
        diff_text: str,
        commit_extensions: set[str],
    ) -> dict[str, int]:
        """Scan diff text for keyword hits across all skills.

        Args:
            diff_text: Diff text (possibly comment-stripped).
            commit_extensions: File extensions in this commit.

        Returns:
            Dict mapping skill names to hit counts.
        """
        hits: dict[str, int] = {}
        for skill_name, pattern_def in SKILL_PATTERNS.items():
            skill_exts = set(pattern_def["file_extensions"])
            if commit_extensions and not (
                commit_extensions & skill_exts
            ):
                continue

            count = self._count_keyword_hits(
                diff_text, pattern_def["keywords"],
            )
            if count > 0:
                hits[skill_name] = count

        return hits

    @staticmethod
    def _strip_comments(
        diff_text: str, extension: str | None,
    ) -> str:
        """Strip comments from diff text for cleaner keyword scanning.

        Args:
            diff_text: Raw diff text.
            extension: File extension (without dot).

        Returns:
            Diff text with comments removed.
        """
        if extension is None:
            return diff_text

        pattern = _COMMENT_PATTERNS.get(extension)
        if pattern is None:
            return diff_text

        return pattern.sub("", diff_text)

    @staticmethod
    def _primary_extension(
        files_changed: list[str],
    ) -> str | None:
        """Get the most common file extension in the commit.

        Args:
            files_changed: List of file paths.

        Returns:
            Most common extension (without dot), or None.
        """
        counts: Counter[str] = Counter()
        for fp in files_changed:
            ext = Path(fp).suffix.lstrip(".").lower()
            if ext:
                counts[ext] += 1
        if counts:
            return counts.most_common(1)[0][0]
        return None

    @staticmethod
    def _count_keyword_hits(
        diff_text: str, keywords: list[str],
    ) -> int:
        """Count how many times any keyword appears in the diff text.

        Most keywords are matched case-sensitively. Keywords containing
        ``.*`` are treated as simple regex-like patterns where ``.*``
        matches any characters on the same line.

        Args:
            diff_text: The raw diff text (added lines).
            keywords: List of keyword strings to search for.

        Returns:
            Total number of keyword matches found.
        """
        count = 0
        for keyword in keywords:
            if ".*" in keyword:
                # Simple pattern: "class.*Error" matches
                # "class MyError"
                parts = keyword.split(".*", 1)
                for line in diff_text.splitlines():
                    prefix_idx = line.find(parts[0])
                    if prefix_idx >= 0:
                        suffix_idx = line.find(
                            parts[1],
                            prefix_idx + len(parts[0]),
                        )
                        if suffix_idx >= 0:
                            count += 1
            else:
                count += diff_text.count(keyword)
        return count

    @staticmethod
    def _get_extensions(
        files_changed: list[str],
    ) -> set[str]:
        """Extract unique file extensions (without dot, lowercase).

        Args:
            files_changed: List of file paths.

        Returns:
            Set of extensions, e.g. ``{"py", "ts"}``.
        """
        exts: set[str] = set()
        for fp in files_changed:
            ext = Path(fp).suffix.lstrip(".").lower()
            if ext:
                exts.add(ext)
        return exts

    @staticmethod
    def _compute_trend(
        month_1_hits: int,
        month_2_hits: int,
        total_hits: int,
    ) -> str:
        """Determine the trend direction for a skill.

        Args:
            month_1_hits: Hits in the most recent month.
            month_2_hits: Hits in the previous month.
            total_hits: Lifetime total hits.

        Returns:
            One of: ``"up"``, ``"down"``, ``"stable"``, ``"new"``.
        """
        if total_hits == 0:
            return "new"
        if month_2_hits == 0 and month_1_hits > 0:
            return "up"
        if month_1_hits == 0 and month_2_hits > 0:
            return "down"
        if month_2_hits == 0 and month_1_hits == 0:
            return "stable"

        ratio = month_1_hits / month_2_hits
        if ratio >= 1.25:
            return "up"
        if ratio <= 0.75:
            return "down"
        return "stable"

    @staticmethod
    def _determine_style(
        ai_ratio: float, avg_commit_size: float,
    ) -> str:
        """Determine the developer's coding style label.

        Args:
            ai_ratio: Fraction of commits classified as AI.
            avg_commit_size: Average number of lines added.

        Returns:
            A style label string.
        """
        if ai_ratio >= 0.5:
            return "ai-augmented"
        if ai_ratio < 0.3 and avg_commit_size < 30:
            return "precise"
        if ai_ratio < 0.3 and avg_commit_size >= 30:
            return "methodical"
        if ai_ratio >= 0.3 and avg_commit_size >= 50:
            return "systematic"
        return "exploratory"
