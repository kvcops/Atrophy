"""atrophy CLI — Typer application with all top-level commands.

Provides commands: init, scan, report, challenge, dashboard.

Security:
    - Email input validated by regex before storing.
    - No shell=True in any subprocess call.
    - All storage calls wrapped in asyncio.run().
    - Errors displayed via Rich panels — no raw tracebacks.
"""

import asyncio
import json
import re
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from atrophy import __version__
from atrophy.config import get_settings
from atrophy.exceptions import AtrophyError, ProviderError

# Force UTF-8 output on Windows to avoid cp1252 encoding errors with
# Rich markup and special characters.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

console = Console()

EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

app = typer.Typer(
    name="atrophy",
    help="Your coding skills have a half-life. atrophy measures it.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ── Helpers ─────────────────────────────────────────────────────────


def _get_storage():
    """Create and return a Storage instance from settings.

    Returns:
        A Storage instance pointing at the configured DB path.
    """
    from atrophy.core.storage import Storage

    settings = get_settings()
    return Storage(settings.db_path)


def _error_panel(message: str) -> None:
    """Print an error message in a styled red panel.

    Args:
        message: The error text to display.
    """
    console.print(
        Panel(
            f"[bold red]{message}[/bold red]",
            title="❌ Error",
            border_style="red",
        )
    )


def _success_panel(message: str) -> None:
    """Print a success message in a styled green panel.

    Args:
        message: The success text to display.
    """
    console.print(
        Panel(
            message,
            title="✅ Done",
            border_style="green",
        )
    )


def _info_panel(message: str, title: str = "ℹ️  Info") -> None:
    """Print an info message in a styled blue panel.

    Args:
        message: The info text to display.
        title: Panel title.
    """
    console.print(
        Panel(
            message,
            title=title,
            border_style="blue",
        )
    )


def _detect_email() -> str | None:
    """Auto-detect the git user email from git config.

    SECURITY: Uses shell=False with a list of arguments and a
    5-second timeout. Never passes user input to subprocess.

    Returns:
        The email string, or None if detection fails.
    """
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],  # noqa: S607
            capture_output=True,
            text=True,
            shell=False,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _validate_email(email: str) -> bool:
    """Validate an email address against the security regex.

    Args:
        email: Email string to validate.

    Returns:
        True if valid, False otherwise.
    """
    return bool(EMAIL_PATTERN.match(email))


def _version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(
            Panel(
                f"[bold green]atrophy[/bold green] v{__version__}",
                title="Version",
                border_style="green",
            )
        )
        raise typer.Exit()


# ── App callback ────────────────────────────────────────────────────


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """atrophy — track your coding skill decay over time."""


# ── COMMAND: atrophy init ───────────────────────────────────────────


@app.command()
def init(
    email: Annotated[
        str | None,
        typer.Option(
            "--email",
            "-e",
            help="Your git author email (auto-detected if omitted).",
        ),
    ] = None,
) -> None:
    """Initialize atrophy tracking for the current git repository."""
    from atrophy.cli.onboarding import run_onboarding

    # Step 1: Run onboarding wizard
    run_onboarding()

    # Step 2: Check we're in a git repo
    cwd = Path.cwd().resolve()
    git_dir = cwd / ".git"
    if not git_dir.exists():
        _error_panel(
            f"Not a git repository: {cwd}\n\n"
            "Run [cyan]git init[/cyan] first, or "
            "[cyan]cd[/cyan] into an existing repo."
        )
        raise typer.Exit(code=1)

    # Step 3: Auto-detect email from git config if not provided
    if email is None:
        detected = _detect_email()
        if detected:
            console.print(
                f"[dim]Detected git email:[/dim] "
                f"[cyan]{detected}[/cyan]"
            )
            email = detected

    # Step 4: Prompt for email if still None
    if email is None:
        email = typer.prompt("Your git author email")

    # Step 5: Validate email format (SECURITY)
    if not _validate_email(email):
        _error_panel(
            f"Invalid email format: [cyan]{email}[/cyan]\n"
            "Expected format: user@domain.tld"
        )
        raise typer.Exit(code=1)

    # Step 6: Save to storage
    project_name = cwd.name
    storage = _get_storage()
    try:
        asyncio.run(_init_project(storage, str(cwd), project_name, email))
    except AtrophyError as exc:
        _error_panel(str(exc))
        raise typer.Exit(code=1) from exc

    # Step 7: Save author_email to settings
    settings = get_settings()
    settings.author_email = email
    settings.save()

    # Step 8: Success panel
    _success_panel(
        f"[bold green]atrophy initialized[/bold green]\n\n"
        f"  Project:   [cyan]{project_name}[/cyan]\n"
        f"  Email:     [cyan]{email}[/cyan]\n"
        f"  Data dir:  [cyan]{settings.data_dir}[/cyan]\n\n"
        "[dim]Next step:[/dim] "
        "Run [bold cyan]atrophy scan[/bold cyan] to analyze your history."
    )


async def _init_project(
    storage, path: str, name: str, email: str
) -> None:
    """Initialise the database and save the project record.

    Args:
        storage: Storage instance.
        path: Absolute path to the git repo.
        name: Human-readable project name.
        email: Author email address.
    """
    await storage.init_db()
    await storage.save_project(path, name, author_email=email)
    await storage.close()


# ── COMMAND: atrophy scan ───────────────────────────────────────────


@app.command()
def scan(
    days: Annotated[
        int,
        typer.Option(
            "--days",
            "-d",
            help="Number of days of history to scan.",
            min=7,
            max=3650,
        ),
    ] = 180,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force re-scan even if scanned recently.",
        ),
    ] = False,
) -> None:
    """Scan git history and analyze commits for AI patterns."""
    try:
        asyncio.run(_run_scan(days, force))
    except AtrophyError as exc:
        _error_panel(str(exc))
        raise typer.Exit(code=1) from exc


async def _run_scan(days: int, force: bool) -> None:
    """Execute the full scan pipeline.

    Args:
        days: Number of days of history to scan.
        force: If True, skip the recent-scan check.
    """
    from atrophy.core.ai_detector import AIDetector
    from atrophy.core.git_scanner import GitScanner
    from atrophy.core.skill_mapper import SkillMapper

    cwd = str(Path.cwd().resolve())
    storage = _get_storage()
    await storage.init_db()

    # Step 1: Load project — must be initialised
    project = await storage.get_project(cwd)
    if project is None:
        await storage.close()
        _error_panel(
            "No project found for this directory.\n"
            "Run [cyan]atrophy init[/cyan] first."
        )
        raise typer.Exit(code=1)

    # Step 2: Check last_scanned_at
    if not force and project.last_scanned_at is not None:
        last = project.last_scanned_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        elapsed = datetime.now(UTC) - last
        if elapsed < timedelta(hours=24):
            hours_ago = round(elapsed.total_seconds() / 3600, 1)
            if not typer.confirm(
                f"Last scanned {hours_ago}h ago. Scan again?"
            ):
                console.print("[dim]Scan skipped.[/dim]")
                await storage.close()
                return

    # Step 3: Run GitScanner
    console.print()
    _info_panel(
        f"Scanning [cyan]{days}[/cyan] days of git history…",
        title="📡 Git Scan",
    )
    scanner = GitScanner(
        cwd, days_back=days, author_email=project.author_email
    )
    commits = scanner.scan_commits()

    if not commits:
        _error_panel("No commits found. Is this the right repo?")
        await storage.close()
        raise typer.Exit(code=1)

    # Step 4: Run AIDetector
    detector = AIDetector()
    analyzed = detector.analyze_batch(commits)

    # Step 5: Run SkillMapper
    mapper = SkillMapper()
    skill_profile = mapper.map_skills(analyzed)
    dead_zones = mapper.get_dead_zones(skill_profile)
    top_skills = mapper.get_strongest_skills(skill_profile)
    coding_dna = mapper.get_coding_dna(analyzed, skill_profile)

    # Step 6: Save to storage
    await storage.upsert_commits(project.id, analyzed)
    await storage.save_skill_snapshots(project.id, skill_profile)

    # Step 7: Update last_scanned_at
    await storage.update_last_scanned(project.id)

    # Save coding DNA as settings for report command
    await storage.set_setting(
        "coding_dna", json.dumps(coding_dna, default=str)
    )

    await storage.close()

    # Step 8: Print summary
    stats = detector.get_summary_stats(analyzed)
    _print_scan_summary(stats, top_skills, dead_zones, skill_profile)


def _print_scan_summary(
    stats: dict,
    top_skills: list[str],
    dead_zones: list[str],
    skill_profile: dict,
) -> None:
    """Print the scan results as a Rich table.

    Args:
        stats: Summary stats from AIDetector.get_summary_stats().
        top_skills: Top skill names.
        dead_zones: Dead zone skill names.
        skill_profile: Full skill profile dict.
    """
    total = stats["total"]
    human = stats["human_count"]
    ai = stats["ai_count"]
    uncertain = stats["uncertain_count"]

    human_pct = f"{human / total * 100:.1f}%" if total else "0%"
    ai_pct = f"{ai / total * 100:.1f}%" if total else "0%"
    uncertain_pct = f"{uncertain / total * 100:.1f}%" if total else "0%"

    # Top skill with emoji and score
    top_skill_display = "—"
    if top_skills:
        top = top_skills[0]
        data = skill_profile.get(top, {})
        emoji = data.get("emoji", "")
        score = data.get("score", 0)
        top_skill_display = f"{emoji} {top} ({score:.0f})"

    settings = get_settings()

    table = Table(
        title="📊 Scan Complete",
        title_style="bold white",
        border_style="cyan",
        show_header=False,
        pad_edge=True,
        padding=(0, 2),
    )
    table.add_column(style="bold", min_width=20)
    table.add_column(min_width=24)

    table.add_row("Commits analyzed", f"[bold]{total}[/bold]")
    table.add_row(
        "Human-written",
        f"[green]{human}[/green]  ({human_pct})",
    )
    table.add_row(
        "AI-assisted",
        f"[red]{ai}[/red]  ({ai_pct})",
    )
    table.add_row(
        "Uncertain",
        f"[yellow]{uncertain}[/yellow]  ({uncertain_pct})",
    )
    table.add_row("Your top skill", top_skill_display)
    table.add_row(
        "Dead zones found",
        f"[red]{len(dead_zones)}[/red]" if dead_zones else "[green]0[/green]",
    )
    table.add_row("Data stored at", f"[dim]{settings.data_dir}[/dim]")

    console.print()
    console.print(table)
    console.print(
        "\n[dim]Tip:[/dim] Run "
        "[bold cyan]atrophy report[/bold cyan]"
        " for your full skill profile.\n"
    )


# ── COMMAND: atrophy report ─────────────────────────────────────────


@app.command()
def report(
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Output raw JSON to stdout (for piping).",
        ),
    ] = False,
    share: Annotated[
        bool,
        typer.Option(
            "--share",
            help="Save a report.md to the current directory.",
        ),
    ] = False,
) -> None:
    """Generate a skill atrophy report."""
    try:
        asyncio.run(_run_report(json_output, share))
    except AtrophyError as exc:
        _error_panel(str(exc))
        raise typer.Exit(code=1) from exc


async def _run_report(json_output: bool, share: bool) -> None:
    """Load data and render the report.

    Args:
        json_output: If True, dump JSON to stdout.
        share: If True, save a report.md file.
    """
    from atrophy.core.skill_mapper import SKILL_PATTERNS

    cwd = str(Path.cwd().resolve())
    storage = _get_storage()
    await storage.init_db()

    # Load project
    project = await storage.get_project(cwd)
    if project is None:
        await storage.close()
        _error_panel(
            "No project found. "
            "Run [cyan]atrophy init[/cyan] then "
            "[cyan]atrophy scan[/cyan] first."
        )
        raise typer.Exit(code=1)

    # Load latest skill snapshots
    snapshots = await storage.get_all_skills_latest(project.id)
    if not snapshots:
        await storage.close()
        _error_panel(
            "No scan data found. "
            "Run [cyan]atrophy scan[/cyan] first."
        )
        raise typer.Exit(code=1)

    # Load coding DNA
    dna_raw = await storage.get_setting("coding_dna")
    coding_dna = json.loads(dna_raw) if dna_raw else {}

    # Load monthly breakdown
    monthly_raw = await storage.get_setting("monthly_breakdown")
    monthly_breakdown = json.loads(monthly_raw) if monthly_raw else {}

    # If no stored monthly, compute from coding_dna or use empty
    if not monthly_breakdown and coding_dna:
        monthly_breakdown = coding_dna.get("monthly_breakdown", {})

    await storage.close()

    # Build the skill profile dict from snapshots
    skill_profile: dict[str, dict] = {}
    for snap in snapshots:
        pattern_def = SKILL_PATTERNS.get(snap.skill_name, {})
        skill_profile[snap.skill_name] = {
            "score": snap.score,
            "last_seen": snap.last_seen,
            "total_hits": snap.total_hits,
            "description": pattern_def.get("description", ""),
            "emoji": pattern_def.get("emoji", ""),
        }

    # Compute dead zones (score < 8 or last_seen > 45 days)
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=45)
    dead_zones: list[str] = []
    for name, data in skill_profile.items():
        ls = data.get("last_seen")
        score = data.get("score", 0)
        if ls is None or score < 8:
            dead_zones.append(name)
        elif ls.tzinfo is None:
            if ls.replace(tzinfo=UTC) < cutoff:
                dead_zones.append(name)
        elif ls < cutoff:
            dead_zones.append(name)

    # ── JSON output ─────────────────────────────────────────────
    if json_output:
        output = {
            "project": project.name,
            "skills": {
                k: {
                    "score": v["score"],
                    "last_seen": (
                        v["last_seen"].isoformat()
                        if v["last_seen"]
                        else None
                    ),
                    "total_hits": v["total_hits"],
                }
                for k, v in skill_profile.items()
            },
            "dead_zones": dead_zones,
            "coding_dna": coding_dna,
        }
        console.print_json(json.dumps(output, default=str))
        return

    # ── Section 1: Skill Profile Table ──────────────────────────
    console.print()
    _print_skill_table(skill_profile, dead_zones)

    # ── Section 2: AI Ratio (monthly chart) ─────────────────────
    if monthly_breakdown:
        console.print()
        _print_monthly_chart(monthly_breakdown)

    # ── Section 3: Dead Zones ───────────────────────────────────
    console.print()
    _print_dead_zones(skill_profile, dead_zones)

    # ── Section 4: Coding DNA ───────────────────────────────────
    console.print()
    _print_coding_dna(coding_dna)

    # ── Share: save report.md ───────────────────────────────────
    if share:
        _save_report_md(skill_profile, dead_zones, coding_dna)


def _print_skill_table(
    skill_profile: dict, dead_zones: list[str]
) -> None:
    """Print Section 1: Skill Profile as a Rich table.

    Args:
        skill_profile: Skill name → data dict.
        dead_zones: List of dead zone skill names.
    """
    table = Table(
        title="🧬 Skill Profile",
        title_style="bold white",
        border_style="cyan",
    )
    table.add_column("Skill", style="bold", min_width=20)
    table.add_column("Score", min_width=12)
    table.add_column("Bar", min_width=20)
    table.add_column("Status", min_width=14)
    table.add_column("Last Used", min_width=14)

    # Sort by score descending
    sorted_skills = sorted(
        skill_profile.items(),
        key=lambda x: x[1]["score"],
        reverse=True,
    )

    now = datetime.now(UTC)

    for skill_name, data in sorted_skills:
        score = data["score"]
        emoji = data.get("emoji", "")
        last_seen = data.get("last_seen")

        # Score color
        if score >= 60:
            score_style = "green"
        elif score >= 30:
            score_style = "yellow"
        else:
            score_style = "red"

        score_text = Text(f"{score:5.1f}", style=f"bold {score_style}")

        # Bar
        bar_filled = int(score / 5)  # 0–20 chars
        bar_empty = 20 - bar_filled
        bar = Text()
        bar.append("█" * bar_filled, style=score_style)
        bar.append("░" * bar_empty, style="dim")

        # Status
        if skill_name in dead_zones:
            status = Text("⚠ DEAD ZONE", style="bold red")
        elif data.get("trend") == "up":
            status = Text("↑ rising", style="green")
        elif data.get("trend") == "down":
            status = Text("↓ falling", style="yellow")
        else:
            status = Text("→ stable", style="dim")

        # Last used
        if last_seen is None:
            last_text = Text("never", style="red")
        else:
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=UTC)
            days_ago = (now - last_seen).days
            if days_ago == 0:
                last_text = Text("today", style="green")
            elif days_ago == 1:
                last_text = Text("yesterday", style="green")
            elif days_ago <= 30:
                last_text = Text(
                    f"{days_ago}d ago", style="green"
                )
            elif days_ago <= 60:
                last_text = Text(
                    f"{days_ago}d ago", style="yellow"
                )
            else:
                last_text = Text(
                    f"{days_ago}d ago", style="red"
                )

        table.add_row(
            f"{emoji} {skill_name}",
            score_text,
            bar,
            status,
            last_text,
        )

    console.print(table)


def _print_monthly_chart(monthly_breakdown: dict) -> None:
    """Print Section 2: Monthly AI ratio chart.

    Args:
        monthly_breakdown: Dict of "YYYY-MM" → {human, ai, uncertain}.
    """
    console.print(
        Panel(
            _build_monthly_bars(monthly_breakdown),
            title="📈 Monthly Human vs AI Ratio",
            border_style="blue",
        )
    )


def _build_monthly_bars(monthly_breakdown: dict) -> str:
    """Build ASCII bar chart of monthly human ratios.

    Args:
        monthly_breakdown: Month → counts dict.

    Returns:
        Formatted multi-line string.
    """
    lines: list[str] = []
    sorted_months = sorted(monthly_breakdown.keys())

    for month in sorted_months:
        counts = monthly_breakdown[month]
        if isinstance(counts, dict):
            human = counts.get("human", 0)
            total = (
                human
                + counts.get("ai", 0)
                + counts.get("uncertain", 0)
            )
        else:
            continue

        if total == 0:
            continue

        ratio = human / total
        pct = int(ratio * 100)
        bar_len = 24
        filled = int(ratio * bar_len)
        empty = bar_len - filled

        # Color based on ratio
        if ratio >= 0.70:
            color = "green"
        elif ratio >= 0.50:
            color = "yellow"
        else:
            color = "red"

        bar = "█" * filled + "░" * empty
        line = f"  {month}  [{color}]{bar}[/{color}]  {pct}% human"
        if ratio < 0.55:
            line += "  [red]← declining[/red]"
        lines.append(line)

    return "\n".join(lines) if lines else "[dim]No monthly data yet.[/dim]"


def _print_dead_zones(
    skill_profile: dict, dead_zones: list[str]
) -> None:
    """Print Section 3: Dead Zones in a red panel.

    Args:
        skill_profile: Skill name → data dict.
        dead_zones: List of dead zone skill names.
    """
    if not dead_zones:
        console.print(
            Panel(
                "[green]No dead zones! "
                "All skills are actively exercised.[/green]",
                title="🎯 Dead Zones",
                border_style="green",
            )
        )
        return

    now = datetime.now(UTC)
    lines = [
        "[bold]Skills you haven't exercised in 45+ days:[/bold]\n"
    ]
    for skill_name in dead_zones:
        data = skill_profile.get(skill_name, {})
        ls = data.get("last_seen")
        emoji = data.get("emoji", "")
        if ls is None:
            ago = "never used"
        else:
            if ls.tzinfo is None:
                ls = ls.replace(tzinfo=UTC)
            days = (now - ls).days
            ago = f"last used: {days} days ago"
        lines.append(f"  [red]•[/red]  {emoji} {skill_name} ({ago})")

    console.print(
        Panel(
            "\n".join(lines),
            title="🎯 Dead Zones",
            border_style="red",
        )
    )


def _print_coding_dna(coding_dna: dict) -> None:
    """Print Section 4: Coding DNA summary.

    Args:
        coding_dna: Dict with primary_language, top_skills, etc.
    """
    if not coding_dna:
        return

    lang = coding_dna.get("primary_language", "unknown")
    style = coding_dna.get("coding_style", "unknown")
    hour = coding_dna.get("most_productive_hour")
    top = coding_dna.get("top_skills", [])
    ai_ratio = coding_dna.get("ai_ratio", 0)

    hour_str = f"{hour}:00" if hour is not None else "unknown"
    top_str = ", ".join(top) if top else "—"

    lines = [
        f"  Primary language: [cyan]{lang}[/cyan]"
        f"  │  Style: [cyan]{style}[/cyan]"
        f"  │  Most active: [cyan]{hour_str}[/cyan]",
        f"  Top skills: [green]{top_str}[/green]",
        f"  AI ratio: [yellow]{ai_ratio:.1%}[/yellow]"
        " of commits AI-assisted",
    ]

    console.print(
        Panel(
            "\n".join(lines),
            title="🧬 Your Coding DNA",
            border_style="magenta",
        )
    )


def _save_report_md(
    skill_profile: dict,
    dead_zones: list[str],
    coding_dna: dict,
) -> None:
    """Save a Markdown report to the current directory.

    Args:
        skill_profile: Skill name → data dict.
        dead_zones: Dead zone skill names.
        coding_dna: Coding DNA summary dict.
    """
    now = datetime.now(UTC)
    lines = [
        "# atrophy Skill Report",
        f"\nGenerated: {now.strftime('%Y-%m-%d %H:%M UTC')}\n",
        "## Skill Profile\n",
        "| Skill | Score | Last Used |",
        "|-------|-------|-----------|",
    ]

    sorted_skills = sorted(
        skill_profile.items(),
        key=lambda x: x[1]["score"],
        reverse=True,
    )

    for name, data in sorted_skills:
        score = data["score"]
        ls = data.get("last_seen")
        ls_str = ls.strftime("%Y-%m-%d") if ls else "never"
        badge = " ⚠️ DEAD ZONE" if name in dead_zones else ""
        lines.append(f"| {name} | {score:.1f}{badge} | {ls_str} |")

    if dead_zones:
        lines.append("\n## Dead Zones\n")
        for name in dead_zones:
            data = skill_profile.get(name, {})
            ls = data.get("last_seen")
            if ls is None:
                ago = "never used"
            else:
                if ls.tzinfo is None:
                    ls = ls.replace(tzinfo=UTC)
                days = (now - ls).days
                ago = f"{days} days ago"
            lines.append(f"- **{name}** — {ago}")

    if coding_dna:
        lines.append("\n## Coding DNA\n")
        lines.append(
            f"- Primary language: {coding_dna.get('primary_language', '?')}"
        )
        lines.append(
            f"- Coding style: {coding_dna.get('coding_style', '?')}"
        )
        lines.append(
            f"- AI ratio: {coding_dna.get('ai_ratio', 0):.1%}"
        )
        top = coding_dna.get("top_skills", [])
        if top:
            lines.append(f"- Top skills: {', '.join(top)}")

    lines.append(
        "\n---\n*Generated by [atrophy]"
        "(https://github.com/atrophy/atrophy)*\n"
    )

    report_path = Path.cwd() / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    _success_panel(
        f"Report saved to [cyan]{report_path}[/cyan]"
    )


# ── Stub commands (not yet implemented) ─────────────────────────────


@app.command()
def challenge(
    generate: Annotated[
        bool,
        typer.Option(
            "--generate",
            "-g",
            help="Generate new challenges for this week.",
        ),
    ] = False,
    done: Annotated[
        int | None,
        typer.Option(
            "--done",
            help="Challenge ID to mark complete",
        ),
    ] = None,
) -> None:
    """Get a coding challenge to exercise a decaying skill."""
    try:
        asyncio.run(_run_challenge(generate, done))
    except AtrophyError as exc:
        _error_panel(str(exc))
        raise typer.Exit(code=1) from exc

async def _run_challenge(generate: bool, done: int | None) -> None:
    """Execute the challenge command flow.

    Args:
        generate: Whether to generate new challenges.
        done: ID of the challenge to mark complete.
    """
    cwd = str(Path.cwd().resolve())
    storage = _get_storage()
    await storage.init_db()

    project = await storage.get_project(cwd)
    if project is None:
        await storage.close()
        _error_panel(
            "No project found. Run [cyan]atrophy init[/cyan] first."
        )
        raise typer.Exit(code=1)

    # ── Handle --done ───────────────────────────────────────────
    if done is not None:
        try:
            await storage.mark_challenge_complete(done)
        except AtrophyError as exc:
            await storage.close()
            _error_panel(str(exc))
            raise typer.Exit(code=1) from exc

        streak = await storage.get_streak(project.id)
        msg_lines = [
            f"[bold green]Challenge #{done} marked complete![/bold green]",
            f"Current streak: [cyan]{streak} weeks[/cyan]"
        ]
        if streak >= 7:
            msg_lines.append(
                "\n[bold orange3]🔥 On fire! You're unstoppable![/bold orange3]"
            )

        _success_panel("\n".join(msg_lines))

        pending = await storage.get_pending_challenges(project.id)
        if not pending:
            console.print(
                "\n[dim]You have no more pending challenges. "
                "Run[/dim] [cyan]atrophy challenge --generate[/cyan]"
                " [dim]to get more.[/dim]"
            )
        await storage.close()
        return

    # ── Handle --generate ───────────────────────────────────────
    if generate:
        from atrophy.core.challenge_engine import ChallengeEngine
        from atrophy.core.git_scanner import GitScanner
        from atrophy.core.skill_mapper import SkillMapper
        from atrophy.providers import get_provider

        latest = await storage.get_latest_challenge_date(project.id)
        now = datetime.now(UTC)
        if latest is not None:
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=UTC)
            if now - latest < timedelta(days=7):
                if not typer.confirm(
                    "You generated challenges less than 7 days ago. "
                    "Generate new ones anyway?"
                ):
                    console.print("[dim]Aborted.[/dim]")
                    await storage.close()
                    return

        # Prepare for generation: load skills, commits, provider
        snapshots = await storage.get_all_skills_latest(project.id)
        if not snapshots:
            await storage.close()
            _error_panel(
                "No scan data found. "
                "Run [cyan]atrophy scan[/cyan] first."
            )
            raise typer.Exit(code=1)

        skill_profile = {
            snap.skill_name: {
                "score": snap.score,
                "last_seen": snap.last_seen,
                "total_hits": snap.total_hits,
            }
            for snap in snapshots
        }

        settings = get_settings()
        try:
            provider = get_provider(settings)
        except ProviderError:
            await storage.close()
            _error_panel(
                "No LLM provider configured.\nRun "
                "[cyan]atrophy config[/cyan] to set one up."
            )
            raise typer.Exit(code=1)

        # Load coding DNA
        dna_raw = await storage.get_setting("coding_dna")
        coding_dna = json.loads(dna_raw) if dna_raw else {}

        language = coding_dna.get("primary_language", "python")
        top_skills = coding_dna.get("top_skills", [])
        top_skill = top_skills[0] if top_skills else "general_programming"

        console.print()
        _info_panel(
            "Generating personalised challenges…",
            title="🧠 AI Challenge Engine"
        )

        scanner = GitScanner(
            cwd, days_back=180, author_email=project.author_email
        )
        commits = scanner.scan_commits()

        mapper = SkillMapper()
        dead_zones = mapper.get_dead_zones(skill_profile)

        engine = ChallengeEngine(provider)

        code_samples = {
            skill: engine.get_code_sample(commits, skill)
            for skill in dead_zones[:3]
        }

        new_challenges = await engine.generate_challenges(
            dead_zones=dead_zones,
            language=language,
            code_samples=code_samples,
            top_skill=top_skill,
        )

        await storage.save_challenges(project.id, new_challenges)
        console.print(
            "\n[bold green]🔥 New challenges added! "
            "Come back next week for more.[/bold green]\n"
        )
        # Fall through to print pending

    # ── Display pending challenges ──────────────────────────────
    pending = await storage.get_pending_challenges(project.id)
    await storage.close()

    if not pending:
        console.print(
            "No active challenges. "
            "Run [cyan]atrophy challenge --generate[/cyan]"
            " to get this week's."
        )
        return

    from atrophy.core.skill_mapper import SKILL_PATTERNS

    console.print()
    for ch in pending:
        diff_color = {
            "easy": "green",
            "medium": "yellow",
            "hard": "red",
        }.get(ch.difficulty.lower(), "blue")

        diff_str = ch.difficulty.upper()
        skill_name = ch.skill_name

        emoji = SKILL_PATTERNS.get(skill_name, {}).get("emoji", "🎯")

        title = Text()
        title.append(
            f" {emoji} {diff_str} · {skill_name} ",
            style=f"bold {diff_color}"
        )

        content = (
            f"[bold cyan]#{ch.id}  \"{ch.title}\"[/bold cyan]\n\n"
            f"{ch.description}\n\n"
            f"Mark done: [cyan]atrophy challenge --done {ch.id}[/cyan]"
        )

        console.print(
            Panel(
                content,
                title=title,
                border_style=diff_color,
            )
        )
        console.print()


@app.command()
def dashboard() -> None:
    """Launch the interactive TUI dashboard."""
    from atrophy.tui.dashboard import AtrophyDashboard

    app_instance = AtrophyDashboard()
    app_instance.run()


@app.command()
def badge(
    port: Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            help="Port to serve the badge API on.",
        ),
    ] = 6174,
) -> None:
    """Serve a local API that returns an SVG skill badge for your README."""
    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import Response

    badge_app = FastAPI(title="atrophy badge API")

    @badge_app.get("/")
    def get_badge():
        """Returns the atrophy SVG badge."""
        # Calculate human ratio
        cwd = str(Path.cwd().resolve())
        storage = _get_storage()
        try:
            asyncio.run(storage.init_db())
            project = asyncio.run(storage.get_project(cwd))

            monthly_breakdown = {}
            h_pct = 0

            if project:
                monthly_raw = asyncio.run(storage.get_setting("monthly_breakdown"))
                monthly_breakdown = json.loads(monthly_raw) if monthly_raw else {}

                if not monthly_breakdown:
                    dna_raw = asyncio.run(storage.get_setting("coding_dna"))
                    coding_dna = json.loads(dna_raw) if dna_raw else {}
                    monthly_breakdown = coding_dna.get("monthly_breakdown", {})

                total_h = 0
                total_all = 0
                for counts in monthly_breakdown.values():
                    if isinstance(counts, dict):
                        h = counts.get("human", 0)
                        a = counts.get("ai", 0)
                        u = counts.get("uncertain", 0)
                        total_h += h
                        total_all += (h + a + u)

                h_pct = int(total_h / total_all * 100) if total_all > 0 else 0
        finally:
            asyncio.run(storage.close())

        if h_pct >= 70:
            color = "#3fb950"  # green
        elif h_pct >= 40:
            color = "#d29922"  # orange
        else:
            color = "#f85149"  # red

        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="160" height="20" role="img" aria-label="atrophy score: {h_pct}%  human">
  <title>atrophy score: {h_pct}%  human</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="160" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="90" height="20" fill="#555"/>
    <rect x="90" width="70" height="20" fill="{color}"/>
    <rect width="160" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="110">
    <text aria-hidden="true" x="460" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="790">atrophy score</text>
    <text x="460" y="140" transform="scale(.1)" fill="#fff" textLength="790">atrophy score</text>
    <text aria-hidden="true" x="1240" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="500">{h_pct}%  human</text>
    <text x="1240" y="140" transform="scale(.1)" fill="#fff" textLength="500">{h_pct}%  human</text>
  </g>
</svg>"""  # noqa: E501
        return Response(content=svg, media_type="image/svg+xml")

    console.print(f"[bold green]Badge served at http://localhost:{port}[/bold green]")
    console.print(f"Add to your README: [cyan]![atrophy score](http://localhost:{port})[/cyan]")
    console.print("[dim](Run `atrophy badge --port XXXX` to change port)[/dim]")

    # SECURITY: Bind only to 127.0.0.1 (localhost)
    uvicorn.run(badge_app, host="127.0.0.1", port=port, log_level="error")


@app.command()
def share(
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Path to save the generated PNG card.",
        ),
    ] = Path("atrophy-card.png"),
) -> None:
    """Generate a shareable PNG card of your skill profile for Twitter/X."""
    try:
        # SECURITY: Path Traversal Prevention
        safe_output = output.resolve()
        cwd = Path.cwd().resolve()

        # Ensure it has a .png extension
        if safe_output.suffix.lower() != ".png":
            _error_panel("Output file must have a .png extension.")
            raise typer.Exit(code=1)

        # Ensure it writes into the current working directory hierarchy
        if not safe_output.is_relative_to(cwd):
            _error_panel(
                "Security Check Failed: Output path must be within the "
                "current working directory."
            )
            raise typer.Exit(code=1)

        asyncio.run(_run_share(safe_output))
    except AtrophyError as exc:
        _error_panel(str(exc))
        raise typer.Exit(code=1) from exc


async def _run_share(safe_output: Path) -> None:
    """Load data and generate the share card PNG."""
    import qrcode
    from PIL import Image, ImageDraw, ImageFont

    cwd = str(Path.cwd().resolve())
    storage = _get_storage()
    await storage.init_db()

    project = await storage.get_project(cwd)
    if not project:
        await storage.close()
        _error_panel("No project found. Run [cyan]atrophy init[/cyan] first.")
        raise typer.Exit(code=1)

    snapshots = await storage.get_all_skills_latest(project.id)
    streak = await storage.get_streak(project.id)

    monthly_raw = await storage.get_setting("monthly_breakdown")
    monthly_breakdown = json.loads(monthly_raw) if monthly_raw else {}
    if not monthly_breakdown:
        dna_raw = await storage.get_setting("coding_dna")
        coding_dna = json.loads(dna_raw) if dna_raw else {}
        monthly_breakdown = coding_dna.get("monthly_breakdown", {})

    await storage.close()

    # Calculate global human / AI percentages
    total_h = 0
    total_a = 0
    total_u = 0

    for counts in monthly_breakdown.values():
        if isinstance(counts, dict):
            total_h += counts.get("human", 0)
            total_a += counts.get("ai", 0)
            total_u += counts.get("uncertain", 0)

    total_all = total_h + total_a + total_u
    h_pct = int(total_h / total_all * 100) if total_all > 0 else 0
    a_pct = int(total_a / total_all * 100) if total_all > 0 else 0

    # Build skill profile
    skill_profile = {
        snap.skill_name: {
            "score": snap.score,
            "last_seen": snap.last_seen,
        }
        for snap in snapshots
    }

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=45)

    dead_zones = []
    active_skills = []

    for name, data in skill_profile.items():
        score = data["score"]
        ls = data["last_seen"]

        is_dead_zone = False
        if ls is None or score < 8:
            is_dead_zone = True
        elif ls.tzinfo is None and ls.replace(tzinfo=UTC) < cutoff:
            is_dead_zone = True
        elif ls.tzinfo is not None and ls < cutoff:
            is_dead_zone = True

        if is_dead_zone:
            dead_zones.append((name, score))
        else:
            active_skills.append((name, score))

    # Sort skills by score descending
    active_skills.sort(key=lambda x: x[1], reverse=True)
    dead_zones.sort(key=lambda x: x[1], reverse=True)

    # Take top 3 + 2 dead zones
    top_active = active_skills[:3]
    top_dead = dead_zones[:2]

    display_skills = top_active + top_dead
    if len(display_skills) < 5:
        idx = 3
        while len(display_skills) < 5 and idx < len(active_skills):
            display_skills.append(active_skills[idx])
            idx += 1

    # -- Image Generation --
    width, height = 1200, 630
    bg_color = (13, 17, 23)  # #0d1117
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Try loading some fonts. We might not have them, so fallback to default
    try:
        font_title = ImageFont.truetype("arial.ttf", 80)
        font_sub = ImageFont.truetype("arial.ttf", 36)
        font_main = ImageFont.truetype("arial.ttf", 32)
        font_small = ImageFont.truetype("arial.ttf", 24)
    except OSError:
        font_title = font_sub = font_main = font_small = ImageFont.load_default()

    # Top-left Title
    draw.text((60, 60), "🧬 atrophy", font=font_title, fill=(255, 255, 255))
    draw.text(
        (60, 160),
        "coding skill health tracker",
        font=font_sub,
        fill=(139, 148, 158),
    )  # #8b949e

    # Background card panel
    panel_y = 240
    draw.rounded_rectangle(
        (60, panel_y, 800, panel_y + 260),
        radius=10,
        fill=(22, 27, 34),
        outline=(48, 54, 61),
    )

    # Center Section: 5 skill bars
    list_y = panel_y + 30
    for name, score in display_skills[:5]:
        is_dz = any(name == dz_name for dz_name, _ in dead_zones)

        # Skill name
        draw.text((90, list_y), name[:20], font=font_main, fill=(201, 209, 217))

        # Bar
        bar_w = 300
        bar_h = 24
        bar_x = 350
        bar_y = list_y + 4

        fill_w = int((score / 100) * bar_w)
        fill_w = max(0, min(bar_w, fill_w))

        score_color = (
            (63, 185, 80)
            if score >= 60
            else ((210, 153, 34) if score >= 30 else (248, 81, 73))
        )

        # Empty part
        draw.rectangle(
            (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), fill=(33, 38, 45)
        )
        # Filled part
        if fill_w > 0:
            draw.rectangle(
                (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), fill=score_color
            )

        # Score label
        draw.text(
            (bar_x + bar_w + 20, list_y),
            f"{score:.0f}",
            font=font_main,
            fill=score_color,
        )

        if is_dz:
            draw.text(
                (bar_x + bar_w + 80, list_y),
                "⚠ DEAD",
                font=font_main,
                fill=(248, 81, 73),
            )

        list_y += 42

    # Bottom Row
    bottom_y = height - 90
    metrics_str = f"Human: {h_pct}% | AI: {a_pct}% | 🔥 {streak}-week streak"
    draw.text((60, bottom_y), metrics_str, font=font_main, fill=(255, 255, 255))

    # QR Code
    repo_url = "https://github.com/atrophy/atrophy" # Placeholder GitHub URL
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(repo_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="white", back_color="#0d1117")

    # Resize and paste qr code
    qr_img = qr_img.resize((150, 150), Image.Resampling.NEAREST)
    img.paste(qr_img, (width - 200, height - 200))

    # Very small watermark
    draw.text(
        (width - 320, height - 40),
        "atrophy · github.com/atrophy",
        font=font_small,
        fill=(139, 148, 158),
    )

    # Save Image
    try:
        img.save(safe_output)
    except Exception as exc:
        raise AtrophyError(f"Failed to save share card: {exc}") from exc

    _success_panel(f"Saved {safe_output} — share it on Twitter/X!")

