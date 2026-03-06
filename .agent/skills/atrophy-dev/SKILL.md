---
name: atrophy-dev
description: Guides development of the atrophy CLI tool — a git history analyzer that tracks which coding skills a developer exercises themselves versus outsources to AI. Use this skill when building, debugging, extending, or testing any part of the atrophy codebase. Activates for tasks involving the git scanner, AI detector, skill mapper, challenge engine, Textual dashboard, LLM providers, or CLI commands.
---

# atrophy Development Skill

## What You Are Building

`atrophy` is a Python CLI tool with one job: analyze a developer's git history, statistically separate human-written commits from AI-generated ones, map the human commits to coding skill categories, and show the developer which skills are decaying from disuse.

The tool is 100% local. No telemetry. No cloud. Everything lives in `~/.atrophy/`.

---

## Architecture Decision Tree

When you receive a task, first identify which layer it belongs to:

```
Is it about reading git commits?
  → git_scanner.py (GitScanner class)

Is it about human vs AI classification?
  → ai_detector.py (AIDetector class)

Is it about categorizing code into skills?
  → skill_mapper.py (SkillMapper class)

Is it about generating exercises with an LLM?
  → challenge_engine.py (ChallengeEngine) + providers/

Is it about storing or retrieving data?
  → storage.py (Storage class, SQLAlchemy 2.0 async)

Is it about a CLI command the user types?
  → cli/app.py (Typer commands)

Is it about the terminal dashboard?
  → tui/dashboard.py (Textual app)

Is it about config or environment variables?
  → config.py (pydantic-settings Settings class)

Is it about types flowing between modules?
  → Check that dicts match the exact field contracts defined below
```

---

## Data Contracts (Canonical Shapes)

These are the exact dict shapes that flow between modules. Maintain these precisely.

### Commit dict (produced by GitScanner, consumed by AIDetector and SkillMapper)
```python
{
    "commit_hash": str,          # 40-char hex SHA
    "author_name": str,
    "author_email": str,
    "timestamp": datetime,       # timezone-aware UTC
    "message": str,
    "files_changed": list[str],  # file paths (relative, basename only in outputs)
    "additions": int,
    "deletions": int,
    "diff_text": str,            # raw diff, added lines only (lines starting with +)
    "minutes_since_prev": float, # minutes since previous commit by same author
    "session_additions": int,    # total lines in this coding session (< 30 min gap)
}
```

### Analyzed commit dict (produced by AIDetector, adds these fields to commit dict)
```python
{
    # ... all commit dict fields above, plus:
    "ai_probability": float,     # 0.0 to 1.0
    "classification": str,       # "human" | "ai" | "uncertain"
    "velocity_score": float,
    "burstiness_score": float,
    "formatting_score": float,
    "message_score": float,
    "entropy_score": float,
}
```

### Skill profile dict (produced by SkillMapper)
```python
{
    "sql_databases": {
        "score": float,          # 0-100
        "last_seen": datetime | None,
        "total_hits": int,
        "recent_hits": int,      # last 30 days
        "trend": str,            # "up" | "down" | "stable" | "new"
        "description": str,
        "emoji": str,
    },
    # ... same shape for all 10 skill keys
}
```

### Challenge dict (produced by ChallengeEngine, stored in DB)
```python
{
    "skill_name": str,
    "difficulty": str,           # "easy" | "medium" | "hard"
    "title": str,                # max 8 words
    "description": str,          # 3-4 sentences
    "estimated_minutes": int,    # 5-120
    "hints": list[str],          # exactly 2 items
    "success_criteria": str,     # one sentence
}
```

---

## The 5 AI Detection Signals

When working on or debugging `ai_detector.py`, always remember these exact weights and logic:

| Signal | Weight | Key Logic |
|--------|--------|-----------|
| velocity | 0.30 | lines/minute. ≥80 → 0.95. <10 → ~0.05 |
| burstiness | 0.25 | CV of line lengths. CV<0.20 → 0.85. CV>0.70 → 0.10 |
| formatting | 0.20 | ratio of "clean" lines (consistent indent, no trailing space) |
| message | 0.15 | conventional commit pattern → 0.75. "fix"/"wip" → 0.05 |
| entropy | 0.10 | Shannon entropy of characters. Low entropy → high AI score |

**Classification thresholds:**
- `ai_probability >= 0.62` → "ai"
- `ai_probability <= 0.38` → "human"
- between → "uncertain"

**Critical disclaimer:** This is a heuristic mirror for self-reflection. It is NOT accurate enough to evaluate others. This disclaimer must appear in the `ai_detector.py` module docstring at all times.

---

## The 10 Skill Categories

When extending or debugging `skill_mapper.py`, the canonical skill keys are:

```
async_concurrency, data_structures, sql_databases, regex_parsing,
error_handling, api_design, testing, algorithms, system_io, security
```

**Recency weights (always apply these):**
- Last 30 days: `3.0x`
- 31-90 days: `2.0x`
- Older: `1.0x`

**Score normalization:** `min(100, weighted_hits * 2.5)`

**Dead zone threshold:** `last_seen` is None OR more than 45 days ago OR score < 8

---

## LLM Provider Pattern

All three providers (`openai_provider.py`, `anthropic_provider.py`, `ollama_provider.py`) implement this abstract interface from `providers/base.py`:

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str, max_tokens: int = 800) -> str:
        """Returns completion text. Raises ProviderError on failure."""
```

When building or fixing a provider:
1. Get API key ONLY via `settings.get_openai_key()` or `settings.get_anthropic_key()` — never hardcode
2. Set timeout: 30 seconds for cloud, 60 seconds for Ollama
3. Wrap ALL API exceptions in `ProviderError` with a user-friendly message
4. For Ollama: validate base URL starts with `http://localhost` or `http://127.0.0.1` (SSRF guard)

---

## Storage Patterns

`storage.py` uses SQLAlchemy 2.0 async exclusively. Always follow this pattern:

```python
async with AsyncSession(self.engine) as session:
    async with session.begin():
        result = await session.execute(
            select(Project).where(Project.path == path)
        )
        project = result.scalar_one_or_none()
```

**The 5 tables:**
- `projects` — one row per initialized repo
- `commits` — one row per commit, upsert by `commit_hash`
- `skill_snapshots` — daily snapshots, unique on `(project_id, snapshot_date, skill_name)`
- `challenges` — generated challenges with completion tracking
- `settings` — key-value store for user preferences

**In tests:** ALWAYS use `"sqlite+aiosqlite:///:memory:"` — NEVER touch `~/.atrophy/atrophy.db`

---

## CLI Command Checklist

When implementing or modifying a Typer command, verify all of these:

- [ ] Command is decorated with `@app.command()`
- [ ] All parameters use `Annotated[type, typer.Option(...)]` syntax (Typer v0.12+)
- [ ] Storage calls wrapped in `asyncio.run()`
- [ ] Missing init state handled: check for project in DB, show "Run atrophy init first" if absent
- [ ] All output goes through `rich.console.Console` — zero bare `print()` calls
- [ ] Errors caught and displayed in a red Rich Panel — never raw tracebacks to user
- [ ] `--help` text is written and useful

---

## Textual Dashboard Rules

The TUI in `tui/dashboard.py` is a `textual.app.App` subclass. Key rules:

- Use `on_mount()` with Textual's worker API for background data loading
- Show loading placeholders (Textual `LoadingIndicator`) while data loads
- Keyboard bindings: `q` → quit, `r` → refresh, `c` → view all challenges
- CSS uses dark theme: background `#0d1117`, card background `#161b22`, border `#30363d`
- Dead zone skill cards: red border `#f85149`
- Human score color: green `#3fb950` if ≥70, orange `#d29922` if 40-70, red `#f85149` if <40
- NEVER use `time.sleep()` or blocking calls inside Textual — use `await asyncio.sleep()` or workers

---

## Security Checklist for Every File

Before finishing any file, mentally run through these:

```
[ ] No shell=True anywhere
[ ] No API keys in strings, logs, or error messages
[ ] No raw SQL string concatenation
[ ] No pickle/marshal/shelve
[ ] All user file paths resolved with Path.resolve() and bounds-checked
[ ] LLM responses sanitized before JSON parsing
[ ] Email inputs validated with regex
[ ] Network servers bind to 127.0.0.1 only
```

---

## Common Mistakes to Avoid

**Mistake 1:** Using `os.system()` or `shell=True` for git commands
→ Always use GitPython's API or `subprocess.run([...], shell=False)`

**Mistake 2:** Storing API keys in `~/.atrophy/config.json`
→ Keys live in environment variables only. `save()` always excludes them.

**Mistake 3:** Blocking the event loop in Textual or async contexts
→ Any slow operation (git scan, LLM call) goes in a Textual worker or `asyncio.run_in_executor()`

**Mistake 4:** Using SQLAlchemy 1.x patterns (`session.query()`, `declarative_base()`)
→ Always use SQLAlchemy 2.0: `select()`, `DeclarativeBase`, `Mapped`, `mapped_column`

**Mistake 5:** Letting GitPython or SQLAlchemy exceptions reach the user
→ Always catch and re-raise as `AtrophyGitError` or `AtrophyStorageError` with a clear message

**Mistake 6:** Generating challenges without sanitizing the LLM JSON response
→ Always strip fences, validate keys, type-check, truncate, and have a hardcoded fallback

**Mistake 7:** Writing tests that use real `~/.atrophy/` paths
→ Always use `tmp_path` fixture or in-memory SQLite

---

## How to Read Existing Files

When asked to extend or fix an existing module:
1. Read the file first — understand the existing class structure
2. Check which other modules consume its output (use the Data Contracts section above)
3. Identify which security rules apply to this file
4. Make the minimal change that solves the problem
5. Run the relevant test in `tests/` mentally to verify nothing broke

---

## Key Commands for Development

```bash
# Install in dev mode
uv sync

# Run atrophy
uv run atrophy --help

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check atrophy/

# Security scan
uv run bandit -r atrophy/ -ll

# Check dependencies for CVEs
uv run pip-audit

# Install pre-commit hooks
uv run pre-commit install
```

---

## Definition of Done (for any task)

A task is complete when:
1. The code follows all rules in the workspace rules file
2. All 8 security checklist items pass
3. The relevant test in `tests/` passes (or a new test is written)
4. `ruff check` passes with zero warnings
5. The feature works end-to-end when invoked via `uv run atrophy [command]`