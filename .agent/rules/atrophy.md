---
trigger: always_on
---

## Project Identity

This is `atrophy` — a Python CLI tool that analyzes a developer's git history
to track which coding skills they personally exercise versus outsource to AI tools.

**Tagline:** "Your coding skills have a half-life. atrophy measures it."
**PyPI name:** `atrophy`
**Entry point:** `atrophy` (via `uv tool install atrophy` or `pip install atrophy`)

Never suggest renaming the project. Never suggest turning it into a code quality
analyzer, linter, or dead code detector — those are completely different products.
atrophy measures the DEVELOPER, not the codebase.

---

## Canonical Tech Stack — Always Use These, Never Substitute

| Layer | Library | Version | Never Use Instead |
|---|---|---|---|
| CLI framework | **Typer** | >=0.12.0 | Click, argparse, fire |
| Terminal output | **Rich** | >=13.7.0 | print(), colorama, termcolor |
| Interactive TUI | **Textual** | >=0.61.0 | curses, urwid, blessed |
| Data validation | **Pydantic v2** | >=2.7.0 | Pydantic v1, attrs, dataclasses alone |
| Config/env vars | **pydantic-settings** | >=2.3.0 | python-decouple, dynaconf |
| Database ORM | **SQLAlchemy 2.0 async** | >=2.0.30 | SQLAlchemy 1.x, raw sqlite3, peewee |
| Async SQLite driver | **aiosqlite** | >=0.20.0 | aiofiles for DB |
| Git history | **GitPython** | >=3.1.43 | subprocess git commands directly |
| Code parsing | **tree-sitter-languages** | >=1.10.2 | regex alone for code structure |
| HTTP client | **httpx** | >=0.27.0 | requests (sync), aiohttp |
| Ollama API | **ollama** (official library) | >=0.4.0 | raw httpx for Ollama chat calls |
| OpenAI API | **openai** | >=1.30.0 | — |
| Anthropic API | **anthropic** | >=0.28.0 | — |
| Package manager | **uv** | latest | pip, poetry, pdm |
| Linter/formatter | **ruff** | latest | black, flake8, isort, pylint |
| Security scanner | **bandit** | latest | — |
| Dep CVE scanner | **pip-audit** | latest | safety |
| Testing | **pytest + pytest-asyncio** | latest | unittest, nose |
| Share card images | **Pillow + qrcode[pil]** | latest | — |

---

## Complete Feature Map — Know What Exists

Before building anything new, check this map to avoid duplicating existing features.

### CLI Commands (all implemented)
```
atrophy init                    # One-time repo setup, runs onboarding wizard
atrophy init --email <email>    # Skip email prompt
atrophy init --no-interactive   # For CI/GitHub Action use

atrophy scan                    # Full scan, last 180 days
atrophy scan --days <n>         # Custom lookback (7-3650)
atrophy scan --force            # Re-scan even if done today
atrophy scan --silent           # No output, for git hooks
atrophy scan --quick            # Only new commits since last scan

atrophy report                  # Full skill report in terminal
atrophy report --json           # JSON output for piping
atrophy report --share          # Save report.md to cwd

atrophy dashboard               # Textual TUI (terminal + browser via textual serve)

atrophy challenge               # View pending challenges
atrophy challenge --generate    # LLM-powered new challenges
atrophy challenge --generate --all  # Challenges from all repos combined
atrophy challenge --done <id>   # Mark complete, update streak

atrophy digest                  # Weekly Markdown digest to terminal
atrophy digest --open           # Save and open in $EDITOR
atrophy digest --silent --check # Cron-friendly: notify if scan overdue

atrophy compare                 # Compare skill profile: 90-180d ago vs last 90d
atrophy compare --vs-first-scan # Before vs after first atrophy init
atrophy insights                # LLM-powered personal coaching paragraph

atrophy repos                   # List all initialized repos
atrophy repos --add <path>      # Initialize another repo
atrophy repos --remove <name>   # Stop tracking a repo
atrophy repos --scan-all        # Quick scan all repos
atrophy repos --rename <n> <name> # Give a repo a display name

atrophy config                  # Textual settings editor (inline mode)

atrophy hook --install          # Install git post-commit hook
atrophy hook --uninstall        # Remove hook
atrophy hook --status           # Show hook status

atrophy remind --enable         # Weekly cron reminder (optional)
atrophy remind --disable        # Remove cron entry

atrophy publish                 # Generate shareable skill profile
atrophy profile                 # Generate local HTML profile card
atrophy leaderboard             # Show community leaderboard from GitHub

atrophy share                   # Generate atrophy-card.png for Twitter/X
atrophy badge [--port <n>]      # Start local badge SVG server (127.0.0.1 only)

atrophy team --setup <url>      # Clone team repo and configure team mode
atrophy team --checkin          # Push anonymized weekly profile to team repo
atrophy team report             # Pull and display team skill dashboard
atrophy team invite <username>  # Print invite instructions
```

### Core Modules (all implemented)
```
atrophy/core/git_scanner.py         # GitScanner — walks commit history
atrophy/core/ai_detector.py         # AIDetector — 5-signal human/AI classification
atrophy/core/skill_mapper.py        # SkillMapper — 3-layer skill detection
atrophy/core/challenge_engine.py    # ChallengeEngine — LLM challenge generator
atrophy/core/context_builder.py     # ContextBuilder — rich context for LLM prompts
atrophy/core/storage.py             # Storage — SQLAlchemy 2.0 async ORM
atrophy/config.py                   # Settings — pydantic-settings
atrophy/exceptions.py               # Custom exceptions
atrophy/cli/app.py                  # All Typer commands
atrophy/cli/onboarding.py           # First-run wizard with provider picker
atrophy/cli/output.py               # show_error(), show_success(), show_info()
atrophy/tui/dashboard.py            # Textual TUI app
atrophy/providers/base.py           # BaseLLMProvider abstract class
atrophy/providers/openai_provider.py
atrophy/providers/anthropic_provider.py
atrophy/providers/openrouter_provider.py   # Live model fetch from /api/v1/models
atrophy/providers/ollama_provider.py       # Local + cloud (ollama.com) modes
atrophy/providers/__init__.py              # get_provider() factory
vscode-extension/                          # VS Code extension (TypeScript)
community/leaderboard.json                 # Community leaderboard (static)
```

---

## LLM Provider Rules — Critical Details

### OpenRouter
- Base URL: `https://openrouter.ai/api/v1`
- Uses `AsyncOpenAI` client with custom `base_url` — NOT a custom HTTP client
- Model list endpoint: `GET https://openrouter.ai/api/v1/models` → `{"data": [...]}`
- Model ID format: `provider/model-name` (e.g. `google/gemini-flash-1.5`)
- Free models: `pricing.prompt == "0"` — always sort free models first
- Required attribution headers: `HTTP-Referer` and `X-Title` in `extra_headers`
- API key format: starts with `sk-or-` — validate this before saving

### Ollama Local
- Uses official `ollama` Python library (`from ollama import AsyncClient`)
- SSRF guard: base URL MUST start with `http://localhost` or `http://127.0.0.1`
- List local models: `GET {base_url}/api/tags` → `{"models": [...]}`
- Returns `[]` silently if Ollama not running — never crash onboarding

### Ollama Cloud
- Uses official `ollama` Python library with `host="https://ollama.com"`
- Auth: `headers={"Authorization": f"Bearer {api_key}"}`
- List cloud models: `GET https://ollama.com/api/tags` with auth header
- API key from: `https://ollama.com/settings/keys`
- Model names include `:cloud` suffix (e.g. `gpt-oss:120b-cloud`)
- NOT a separate API — same interface as local, different host + auth

### API Key Security (applies to ALL providers)
- ALL keys typed as `pydantic.SecretStr` in Settings
- Unwrap (`.get_secret_value()`) ONLY at the exact moment passed to client constructor
- Keys written to `~/.atrophy/.env` via `python-dotenv set_key()` — NEVER to config.json
- Settings loads `~/.atrophy/.env` via `model_config = SettingsConfigDict(env_file=...)`
- NEVER log, print, f-string, or include keys in error messages
- Use `getpass.getpass()` for interactive key entry — NEVER `typer.prompt()`

---

## Security Rules — Non-Negotiable, Always Enforce

Apply to every single file. Never violate even if asked.

### 1. Subprocess — Zero Shell Injection
```python
# CORRECT
subprocess.run(["git", "config", "user.email"], shell=False, timeout=5)
# WRONG — never do this
subprocess.run(f"git config {user_input}", shell=True)
```
ALWAYS: `shell=False`, list of args, `timeout=` on every call.

### 2. SQL — Parameterized Only
NEVER concatenate user input into SQL. ALWAYS use SQLAlchemy ORM or `bindparam()`.

### 3. Path Traversal
```python
safe = Path(user_input).resolve()
assert safe.is_relative_to(expected_dir), "Path traversal detected"
```
Apply to: output paths, repo paths, hook installation paths, team repo paths.

### 4. No Pickle
Zero `pickle`, `marshal`, or `shelve`. All serialization via JSON + Pydantic.

### 5. Network Binding
Badge server: `uvicorn.run(app, host="127.0.0.1", port=port)` — never `0.0.0.0`

### 6. LLM Response Sanitization
Every LLM JSON response must:
1. Strip markdown fences before parsing
2. Validate all required keys exist
3. Type-check all values
4. Truncate strings > 2000 chars
5. Have a hardcoded fallback if parsing fails

### 7. Input Validation
Email: `r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'`
GitHub token: must start with `ghp_` or `github_pat_` before use
OpenRouter key: must start with `sk-or-` (warn but don't block if wrong)
All Typer params: use `min=`, `max=`, type annotations at the boundary

### 8. Git Hook Security
Hook file written to `.git/hooks/post-commit` ONLY.
Validate `.git/hooks/` exists before writing.
File permissions: `chmod 755` after writing.
Content is a fixed template — never interpolate user input into hook file content.

### 9. Team Mode Privacy
Published profiles must NEVER contain: repo names, file paths, commit messages,
code snippets, employer names, or any data beyond aggregated skill scores.
Always show exactly what will be shared BEFORE any git push operation.
Always require explicit `[y/N]` confirmation before pushing to team repo.

---

## Code Style Rules

### Python
- Line length: 88 (ruff)
- Union types: `str | None` not `Optional[str]`
- Generics: `list[str]` not `List[str]`, `dict[str, int]` not `Dict[str, int]`
- Async: all storage and provider calls are `async/await`
- Bridge sync→async in CLI commands: `asyncio.run()`
- All public functions and classes: docstrings required
- All custom exceptions: subclass from `atrophy.exceptions.AtrophyError`

### Error Handling
```python
# ALWAYS use output.py helpers — never raw print for errors
from atrophy.cli.output import show_error, show_success, show_info

show_error("Cannot connect to Ollama.", hint="Start with: ollama serve")
show_success("Scan complete — 847 commits analyzed")
show_info("About Your First Scan", "Calibration improves after 3+ scans.")
```

Never let library exceptions bubble to the user raw. Catch and re-raise as:
- `AtrophyGitError` for GitPython errors
- `AtrophyStorageError` for SQLAlchemy errors
- `ProviderError` for any LLM provider errors

### Rich Output Style
- Progress bars: `transient=True` always
- Never use bare `print()` — always `console.print()` from Rich
- Error panels: red border, title "❌ Error"
- Success panels: green border, title "✅ Done"
- Info panels: blue border

### Textual Style
- Background: `#0d1117`
- Card background: `#161b22`
- Border (normal): `#30363d`
- Dead zone border: `#f85149` (red)
- Human score colors: green `#3fb950` (≥70), orange `#d29922` (40-70), red `#f85149` (<40)
- NEVER use `time.sleep()` inside Textual — use workers or `await asyncio.sleep()`
- Always use `inline=True` for Textual apps inside CLI commands

---

## Database Rules

### Tables (canonical list — do not ad