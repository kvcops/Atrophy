---
trigger: always_on
---

## Project Identity

This is `atrophy` — a Python CLI tool that analyzes a developer's git history to track which coding skills they are personally exercising versus outsourcing to AI tools. The PyPI package name is `atrophy`. The GitHub repo is `atrophy`. Never suggest renaming it.

Tagline: *"Your coding skills have a half-life. atrophy measures it."*

---

## Tech Stack — Always Use These, Never Substitute

- **Python 3.11+** — use modern syntax: `match`, `tomllib`, `ExceptionGroup`, `X | Y` union types
- **uv** — package manager. Never suggest `pip install` to the user. Always use `uv add`, `uv run`, `uv sync`
- **Typer** — CLI framework. Never use Click, argparse, or any other CLI library
- **Pydantic v2** — all data models and config. Use `model_validator`, `field_validator`, `SecretStr`. Never use Pydantic v1 syntax (`@validator`, `class Config`)
- **pydantic-settings** — for all environment variable and config file handling
- **SQLAlchemy 2.0 async** — ORM only. Use `mapped_column`, `Mapped`, `DeclarativeBase`, `AsyncSession`. Never use SQLAlchemy 1.x patterns
- **aiosqlite** — async SQLite driver
- **GitPython** — git history access
- **Textual** — TUI dashboard. Never suggest building a separate web server for the dashboard
- **Rich** — all terminal output styling (progress bars, tables, panels, color)
- **tree-sitter** — code parsing for skill detection
- **httpx** — async HTTP client for Ollama provider
- **Pillow + qrcode** — share card PNG generation

---

## Security Rules — Non-Negotiable, Always Enforce

These rules apply to every single file. Never write code that violates them, even if asked.

### 1. Subprocess — Zero Shell Injection
- ALWAYS use `shell=False` with a list of arguments
- ALWAYS add `timeout=` to every subprocess call
- NEVER pass user-supplied strings into subprocess via f-strings or concatenation
- ✅ Correct: `subprocess.run(["git", "config", "user.email"], shell=False, timeout=5)`
- ❌ Wrong: `subprocess.run(f"git config {user_input}", shell=True)`

### 2. API Keys — SecretStr Only
- ALL API keys MUST be typed as `pydantic.SecretStr`
- Keys are ONLY unwrapped (`.get_secret_value()`) at the exact moment they're passed to the LLM client constructor — nowhere else
- NEVER log, print, f-string, or include API keys in error messages
- NEVER write API keys to disk in config files — `save()` must always `exclude={"openai_api_key", "anthropic_api_key"}`
- Use `getpass.getpass()` (NOT `typer.prompt`) when asking users to enter API keys interactively

### 3. SQL — Parameterized Queries Only
- NEVER concatenate user input into SQL strings
- ALWAYS use SQLAlchemy ORM methods or `bindparam()`
- If you see raw string formatting in a SQL context, flag it immediately and rewrite it

### 4. Path Traversal Prevention
- ALWAYS resolve user-supplied file paths: `safe = Path(user_input).resolve()`
- ALWAYS verify the resolved path is within the expected directory before using it
- Use `Path.resolve()` then check `safe.is_relative_to(expected_dir)`

### 5. No Pickle — Ever
- NEVER use `pickle`, `marshal`, or `shelve` anywhere in this codebase
- All serialization uses JSON + Pydantic `.model_dump()` / `.model_validate()`

### 6. Network Binding
- The badge FastAPI server MUST bind to `127.0.0.1` only, never `0.0.0.0`
- The Ollama provider URL MUST be validated to start with `http://localhost` or `http://127.0.0.1` before use (SSRF prevention)

### 7. LLM Response Sanitization
- ALWAYS strip markdown fences before JSON parsing LLM output
- ALWAYS validate all required keys exist after parsing
- ALWAYS type-check parsed values
- ALWAYS truncate string fields longer than 2000 characters
- ALWAYS wrap LLM response parsing in try/except with a hardcoded safe fallback

### 8. Input Validation
- ALWAYS validate email addresses with regex before storing:
  `r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'`
- ALWAYS use Typer's `min=`, `max=`, and type annotations to validate CLI inputs at the boundary

---

## Code Style Rules

### Python Style
- Line length: 88 characters (ruff default)
- Use `ruff` for linting and formatting — never `black`, `flake8`, or `pylint`
- All public functions and classes MUST have docstrings
- Use `|` union syntax for types: `str | None`, NOT `Optional[str]`
- Use `list[str]` not `List[str]`, `dict[str, int]` not `Dict[str, int]`
- All async functions must be properly awaited — never mix sync/async incorrectly
- Use `asyncio.run()` in CLI commands to bridge sync Typer → async storage/engine

### Naming Conventions
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions and variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Never abbreviate beyond industry standards (e.g., `db` is fine, `sk_map` is not)

### Error Handling
- ALWAYS use custom exceptions from `atrophy.exceptions` (create this module if it doesn't exist)
- Custom exceptions: `AtrophyError`, `AtrophyStorageError`, `AtrophyGitError`, `ProviderError`
- NEVER let library exceptions (GitCommandError, sqlalchemy errors) bubble up raw to the user
- Catch them, wrap in the appropriate `AtrophyError` subclass, and show a Rich-formatted user-friendly message

### Rich Output Style
- Progress bars: use `transient=True` so they disappear after completion
- All error output: red `rich.panel.Panel` with title "❌ Error"
- All success output: green `rich.panel.Panel` with title "✅ Done"
- All info output: blue `rich.panel.Panel`
- Never use `print()` directly — always `rich.print()` or `console.print()`

---

## Project Structure Rules

The canonical folder structure is:
```
atrophy/
├── atrophy/
│   ├── __init__.py
│   ├── exceptions.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   └── onboarding.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── git_scanner.py
│   │   ├── ai_detector.py
│   │   ├── skill_mapper.py
│   │   ├── challenge_engine.py
│   │   └── storage.py
│   ├── config.py
│   ├── tui/
│   │   ├── __init__.py
│   │   └── dashboard.py
│   └── providers/
│       ├── __init__.py
│       ├── base.py
│       ├── openai_provider.py
│       ├── anthropic_provider.py
│       └── ollama_provider.py
├── tests/
├── .pre-commit-config.yaml
├── pyproject.toml
├── SECURITY.md
├── CONTRIBUTING.md
├── built-with-atrophy.md
└── README.md
```

- NEVER create files outside this structure without asking
- NEVER create a `requirements.txt` — use `pyproject.toml` only
- NEVER create a `setup.py` — this is a modern `pyproject.toml`-only project

---

## Testing Rules

- Test framework: `pytest` + `pytest-asyncio`
- All async tests use `@pytest.mark.asyncio`
- Test files live in `tests/` and mirror the `atrophy/` structure
- Minimum: every public method in `core/` has at least one test
- Use in-memory SQLite (`:memory:`) for storage tests — never touch the real `~/.atrophy/atrophy.db` in tests
- Use `tmp_path` pytest fixture for any file system tests
- Mock all external calls (LLM providers, git) in unit tests

---

## Commit Message Convention

- `feat:` new feature
- `fix:` bug fix
- `security:` security fix (prioritize reviewing these)
- `test:` adding tests
- `docs:` documentation only
- `refactor:` no behavior change
- `chore:` tooling, dependencies

---

## What atrophy Does NOT Do (Never Add These)

- No telemetry, analytics, or phone-home of any kind
- No cloud sync or remote storage
- No data collection beyond what's stored in `~/.atrophy/` locally
- No web scraping
- No reading files outside the target git repository
- No writing to the target repository (read-only git access always)