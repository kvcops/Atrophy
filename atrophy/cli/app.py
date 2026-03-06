"""atrophy CLI — Typer application with all top-level commands.

Provides commands: init, scan, report, challenge, config, dashboard.

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
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from atrophy import __version__
from atrophy.cli.output import (
    console,
    show_banner,
    show_error,
    show_info,
    show_success,
)
from atrophy.config import get_settings
from atrophy.exceptions import AtrophyError, ProviderError

# Force UTF-8 output on Windows to avoid cp1252 encoding errors with
# Rich markup and special characters.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

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
    show_banner()

    from atrophy.cli.onboarding import run_onboarding

    # Step 1: Run onboarding wizard
    run_onboarding()

    # Step 2: Check we're in a git repo
    cwd = Path.cwd().resolve()
    git_dir = cwd / ".git"
    if not git_dir.exists():
        show_error(
            f"Not a git repository: {cwd}",
            hint="Run `git init` first, or cd into an existing repo.",
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
        show_error(
            f"Invalid email format: {email}",
            hint="Expected format: user@domain.tld",
        )
        raise typer.Exit(code=1)

    # Step 6: Save to storage
    project_name = cwd.name
    storage = _get_storage()
    try:
        asyncio.run(_init_project(storage, str(cwd), project_name, email))
    except AtrophyError as exc:
        show_error(str(exc))
        raise typer.Exit(code=1) from exc

    # Step 7: Save author_email to settings
    settings = get_settings()
    settings.author_email = email
    settings.save()

    # Step 8: Success panel
    show_success(
        f"[bold]atrophy initialized[/bold]\n\n"
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
    show_banner()
    try:
        asyncio.run(_run_scan(days, force))
    except AtrophyError as exc:
        show_error(str(exc))
        raise typer.Exit(code=1) from exc


def _build_scan_left_panel(
    processed: int,
    total: int,
    phase: str,
    current_msg: str,
) -> Panel:
    """Build the left panel for the live scan dashboard.

    Args:
        processed: Number of commits processed so far.
        total: Total commits to process.
        phase: Current phase description.
        current_msg: Current commit message snippet.

    Returns:
        A styled Rich Panel.
    """
    bar_width = 30
    ratio = processed / total if total else 0
    filled = int(ratio * bar_width)
    empty = bar_width - filled
    bar = f"[cyan]{'█' * filled}[/cyan][dim]{'░' * empty}[/dim]"

    body = (
        f"  {bar}  {processed:,} / {total:,}\n"
        f"  Phase: [bold]{phase}[/bold]\n"
        f"  Current: [dim]{current_msg[:48]}[/dim]"
    )
    return Panel(
        body,
        title="[bold]📡 Scanning commits[/bold]",
        border_style="cyan",
    )


def _build_scan_right_panel(
    human: int, ai: int, uncertain: int, top_skill: str,
    dead_count: int,
) -> Panel:
    """Build the right stats panel for the live scan dashboard.

    Args:
        human: Human commit count so far.
        ai: AI commit count so far.
        uncertain: Uncertain commit count so far.
        top_skill: Current top skill name.
        dead_count: Number of dead zones so far.

    Returns:
        A styled Rich Panel.
    """
    total = human + ai + uncertain
    h_pct = int(human / total * 100) if total else 0
    a_pct = int(ai / total * 100) if total else 0
    u_pct = int(uncertain / total * 100) if total else 0

    def mini_bar(pct: int, color: str) -> str:
        """Build a tiny 10-char bar."""
        filled = pct // 10
        empty = 10 - filled
        return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"

    body = (
        f"  Human so far:   {mini_bar(h_pct, 'green')}  {h_pct}%\n"
        f"  AI so far:      {mini_bar(a_pct, 'red')}  {a_pct}%\n"
        f"  Uncertain:      {mini_bar(u_pct, 'yellow')}  {u_pct}%\n"
        f"\n"
        f"  Top skill: [cyan]{top_skill}[/cyan]\n"
        f"  Dead zones: [red]{dead_count}[/red]"
    )
    return Panel(
        body,
        title="[bold]📊 Live Stats[/bold]",
        border_style="blue",
    )


async def _run_scan(days: int, force: bool) -> None:
    """Execute the full scan pipeline with live dashboard.

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
        show_error(
            "No project found for this directory.",
            hint="Run `atrophy init` first.",
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
    scanner = GitScanner(
        cwd, days_back=days, author_email=project.author_email
    )
    commits = scanner.scan_commits()

    if not commits:
        show_error(
            "No commits found. Is this the right repo?",
            hint="Check the --days flag or your git email.",
        )
        await storage.close()
        raise typer.Exit(code=1)

    total = len(commits)

    # Step 4 + 5: Classify and map with live dashboard
    detector = AIDetector()

    detector.group_into_sessions(commits)
    baseline = detector.build_baseline(commits, cwd)
    baseline_data = {
        "avg_velocity": baseline.avg_velocity,
        "uses_conventional_commits": baseline.uses_conventional_commits,
        "uses_autoformatter": baseline.uses_autoformatter,
        "avg_commit_size": baseline.avg_lines_per_commit,
    }
    await storage.save_baseline(project.id, baseline_data)

    from atrophy.config import get_settings
    from atrophy.core.skill_classifier import LLMSkillClassifier
    from atrophy.exceptions import ProviderError
    from atrophy.providers import get_provider

    llm_classifier = None
    try:
        settings_obj = get_settings()
        provider = get_provider(settings_obj)
        llm_classifier = LLMSkillClassifier(provider)
    except ProviderError:
        # It's fine to scan without an LLM; Layer 2 classification is just skipped
        pass

    mapper = SkillMapper(llm_classifier=llm_classifier)

    analyzed: list[dict] = []
    live_human = 0
    live_ai = 0
    live_uncertain = 0
    live_top_skill = "—"
    live_dead_count = 0

    layout = Layout()
    layout.split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=1),
    )

    layout["left"].update(
        _build_scan_left_panel(0, total, "Starting…", "")
    )
    layout["right"].update(
        _build_scan_right_panel(0, 0, 0, "—", 0)
    )

    with Live(
        layout, console=console, refresh_per_second=4,
        transient=True,
    ):
        for i, commit in enumerate(commits):
            result = detector.analyze(commit, baseline)
            analyzed.append(result)

            cls = result.get("classification", "uncertain")
            if cls == "human":
                live_human += 1
            elif cls == "ai":
                live_ai += 1
            else:
                live_uncertain += 1

            # Update dashboard every 50 commits or at the end
            if (i + 1) % 50 == 0 or (i + 1) == total:
                # Compute intermediate skill profile
                human_commits = [
                    c for c in analyzed
                    if c.get("classification") == "human"
                ]
                if human_commits:
                    sp = mapper.map_skills(human_commits)
                    strongest = mapper.get_strongest_skills(sp)
                    live_top_skill = (
                        strongest[0] if strongest else "—"
                    )
                    live_dead_count = len(
                        mapper.get_dead_zones(sp)
                    )

                phase = (
                    "Classifying commits…"
                    if (i + 1) < total
                    else "Finalising…"
                )
                msg_snippet = commit.get("message", "")[:48]

                layout["left"].update(
                    _build_scan_left_panel(
                        i + 1, total, phase, msg_snippet,
                    )
                )
                layout["right"].update(
                    _build_scan_right_panel(
                        live_human, live_ai, live_uncertain,
                        live_top_skill, live_dead_count,
                    )
                )

    # Step 5: Final skill mapping
    skill_profile = mapper.map_skills(analyzed)
    dead_zones = mapper.get_dead_zones(skill_profile)
    top_skills = mapper.get_strongest_skills(skill_profile)
    coding_dna = mapper.get_coding_dna(analyzed, skill_profile)

    # Step 6: Save to storage and detect wins
    old_snapshots = await storage.get_all_skills_latest(project.id)
    old_profile = {
        s.skill_name: {"score": s.score, "last_seen": s.snapshot_date}
        for s in old_snapshots
    }
    
    wins = await storage.detect_and_save_wins(project.id, old_profile, skill_profile)

    await storage.upsert_commits(project.id, analyzed)
    await storage.save_skill_snapshots(project.id, skill_profile)

    # Step 7: Update last_scanned_at and scan_count
    await storage.update_last_scanned(project.id)
    
    scan_count_str = await storage.get_setting("scan_count", "0")
    scan_count = int(scan_count_str) + 1
    await storage.set_setting("scan_count", str(scan_count))

    # Save coding DNA as settings for report command
    await storage.set_setting(
        "coding_dna", json.dumps(coding_dna, default=str)
    )

    await storage.close()

    if scan_count < 3:
        console.print(
            Panel(
                "[dim]atrophy needs 2-3 scans over a few weeks to calibrate "
                "your personal baseline. Your first reports may show lower scores "
                "than reality — that's normal.[/dim]\n\n"
                "[dim]The tool gets smarter about YOU over time. Run "
                "[bold]atrophy scan[/bold] weekly for the best results.[/dim]",
                title="📊 About your early scans",
                border_style="yellow",
                expand=False,
            )
        )
    elif scan_count == 3:
        console.print(
            Panel(
                "📈 [green]atrophy is now calibrated to your coding style.[/green]",
                border_style="green",
                expand=False,
            )
        )

    # Step 8: Print summary
    stats = detector.get_summary_stats(analyzed)
    detection_stats = mapper.get_detection_stats()
    _print_scan_summary(
        stats, top_skills, dead_zones, skill_profile, detection_stats, wins
    )


def _print_scan_summary(
    stats: dict,
    top_skills: list[str],
    dead_zones: list[str],
    skill_profile: dict,
    detection_stats: dict | None = None,
    wins: list | None = None,
) -> None:
    """Print the scan results as a Rich table.

    Args:
        stats: Summary stats from AIDetector.get_summary_stats().
        top_skills: Top skill names.
        dead_zones: Dead zone skill names.
        skill_profile: Full skill profile dict.
        detection_stats: Detection method counts.
        wins: List of Win objects to celebrate.
    """
    total = stats["total"]
    human = stats["human_count"]
    ai = stats["ai_count"]
    uncertain = stats["uncertain_count"]

    human_pct = f"{human / total * 100:.1f}%" if total else "0%"
    ai_pct = f"{ai / total * 100:.1f}%" if total else "0%"
    uncertain_pct = (
        f"{uncertain / total * 100:.1f}%" if total else "0%"
    )

    # Top skill with emoji and score
    top_skill_display = "—"
    if top_skills:
        top = top_skills[0]
        data = skill_profile.get(top, {})
        emoji = data.get("emoji", "")
        score = data.get("score", 0)
        top_skill_display = f"{emoji} {top} ({score:.0f})"

    # Display Wins first!
    if wins:
        win_lines = []
        for w in wins:
            if w.win_type == "skill_improved":
                win_lines.append(f"✨ {w.message}")
            elif w.win_type == "dead_zone_cleared":
                win_lines.append(f"🔥 {w.message}")
            elif w.win_type == "new_skill_detected":
                win_lines.append(f"🌱 {w.message}")
            else:
                win_lines.append(f"🎉 {w.message}")
        
        console.print(
            Panel(
                "\n".join(win_lines),
                title="[bold green]🎉 You improved this week![/bold green]",
                border_style="green",
                expand=False,
            )
        )

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

    table.add_row(
        "Skill Exercise Rate",
        f"[green]{human_pct}[/green]",
    )
    table.add_row(
        "AI-assisted commits",
        f"[red]{ai}[/red] ({ai_pct}) (scaffolding/boilerplate)",
    )
    table.add_row(
        "Uncertain",
        f"[yellow]{uncertain}[/yellow]  ({uncertain_pct})",
    )
    table.add_row("Your top skill", top_skill_display)
    table.add_row(
        "Needs Practice zones",
        f"[red]{len(dead_zones)}[/red]"
        if dead_zones
        else "[green]0[/green]",
    )
    table.add_row(
        "Data stored at", f"[dim]{settings.data_dir}[/dim]",
    )

    if detection_stats:
        ast = detection_stats.get("ast", 0)
        llm = detection_stats.get("llm", 0)
        kw = detection_stats.get("keyword", 0)
        table.add_row(
            "Detection method",
            f"[dim]{ast} AST  \u00b7  {llm} LLM  \u00b7  {kw} Keyword[/dim]",
        )

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
    if not json_output:
        show_banner()
    try:
        asyncio.run(_run_report(json_output, share))
    except AtrophyError as exc:
        show_error(str(exc))
        raise typer.Exit(code=1) from exc


async def _run_report(json_output: bool, share: bool) -> None:
    """Load data and render the report with animated reveal.

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
        show_error(
            "No project found.",
            hint="Run `atrophy init` then `atrophy scan` first.",
        )
        raise typer.Exit(code=1)

    # Load latest skill snapshots
    snapshots = await storage.get_all_skills_latest(project.id)
    if not snapshots:
        await storage.close()
        show_error(
            "No scan data found.",
            hint="Run `atrophy scan` first.",
        )
        raise typer.Exit(code=1)

    # Load coding DNA
    dna_raw = await storage.get_setting("coding_dna")
    coding_dna = json.loads(dna_raw) if dna_raw else {}

    # Load monthly breakdown
    monthly_raw = await storage.get_setting("monthly_breakdown")
    monthly_breakdown = (
        json.loads(monthly_raw) if monthly_raw else {}
    )

    # If no stored monthly, compute from coding_dna or use empty
    if not monthly_breakdown and coding_dna:
        monthly_breakdown = coding_dna.get(
            "monthly_breakdown", {}
        )

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

    # ── Section 1: Animated Skill Profile Table ─────────────────
    console.print()
    _print_skill_table_animated(skill_profile, dead_zones)

    # ── Section 1.5: ASCII Skill Radar ──────────────────────────
    time.sleep(0.1)
    _print_skill_radar(skill_profile, dead_zones)

    # ── Section 2: Animated AI Ratio Timeline ───────────────────
    if monthly_breakdown:
        time.sleep(0.1)
        console.print()
        _print_monthly_chart_animated(monthly_breakdown)

    # ── Section 3: Skills to Revisit (flash effect) ────────────────────
    time.sleep(0.1)
    console.print()
    _print_dead_zones_flash(skill_profile, dead_zones)

    # ── Section 4: Coding DNA ───────────────────────────────────
    time.sleep(0.1)
    console.print()
    _print_coding_dna(coding_dna)

    console.print(
        "\n[dim]Note: These are statistical estimates for self-reflection only.\n"
        "Squash commits, auto-formatters, and conventional commit tools may affect readings.\n"
        "Baseline calibration improves accuracy over time.[/dim]"
    )

    # ── Share: save report.md ───────────────────────────────────
    if share:
        _save_report_md(skill_profile, dead_zones, coding_dna)


def _print_skill_table_animated(
    skill_profile: dict, dead_zones: list[str],
) -> None:
    """Print Section 1: Skill Profile with rows appearing one at a time.

    Args:
        skill_profile: Skill name → data dict.
        dead_zones: List of dead zone skill names.
    """
    now = datetime.now(UTC)

    # Sort by score descending
    sorted_skills = sorted(
        skill_profile.items(),
        key=lambda x: x[1]["score"],
        reverse=True,
    )

    # Build rows first
    rows: list[tuple] = []
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

        score_text = Text(
            f"{score:5.1f}", style=f"bold {score_style}",
        )

        # Bar
        bar_filled = int(score / 5)  # 0–20 chars
        bar_empty = 20 - bar_filled
        bar = Text()
        bar.append("█" * bar_filled, style=score_style)
        bar.append("░" * bar_empty, style="dim")

        # Status
        if skill_name in dead_zones:
            status = Text("⚡ Needs Practice", style="bold red")
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
                    f"{days_ago}d ago", style="green",
                )
            elif days_ago <= 60:
                last_text = Text(
                    f"{days_ago}d ago", style="yellow",
                )
            else:
                last_text = Text(
                    f"{days_ago}d ago", style="red",
                )

        rows.append((
            f"{emoji} {skill_name}",
            score_text,
            bar,
            status,
            last_text,
        ))

    # Animate: add rows one by one with delay
    with Live(console=console, refresh_per_second=20) as live:
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

        for row in rows:
            table.add_row(*row)
            live.update(table)
            time.sleep(0.05)

        # Final flash
        time.sleep(0.15)
    console.print(table)


def _print_skill_radar(
    skill_profile: dict, dead_zones: list[str],
) -> None:
    """Print a mini ASCII skill radar / star visualization.

    Shows top 6 skills radiating from a center point "YOU",
    with dead zones marked with dotted lines and ⚠.

    Args:
        skill_profile: Skill name → data dict.
        dead_zones: Dead zone skill names.
    """
    sorted_skills = sorted(
        skill_profile.items(),
        key=lambda x: x[1]["score"],
        reverse=True,
    )

    # Take top 6 skills for the radar
    radar_skills = sorted_skills[:6]
    if len(radar_skills) < 3:
        return  # Not enough data

    # Pad to 6
    while len(radar_skills) < 6:
        radar_skills.append(("—", {"score": 0}))

    # Layout: 6 directions
    # Positions: top, top-right, bottom-right, bottom,
    #            bottom-left, top-left
    names = [s[0] for s in radar_skills]
    scores = [s[1]["score"] for s in radar_skills]

    # Build the radar as styled text
    def _arm(
        name: str, score: float, is_dead: bool,
    ) -> str:
        """Generate arm label."""
        length = int(score / 20) + 1  # 1-5 chars
        if is_dead:
            line = "┄" * length
            return (
                f"[red]{line} {name} ← ⚠ DEAD[/red]"
            )
        line = "━" * length
        return f"[cyan]{line} {name}[/cyan]"

    top = names[0]
    top_dead = top in dead_zones
    right = names[1]
    right_dead = right in dead_zones
    bottom = names[2]
    bottom_dead = bottom in dead_zones
    left = names[3]
    left_dead = left in dead_zones
    tr = names[4]
    tr_dead = tr in dead_zones
    bl = names[5]
    bl_dead = bl in dead_zones

    # Simple 10-line radar
    lines = [
        "",
        f"              {_arm(top, scores[0], top_dead)}",
        "                \u2502",
        (
            f"   {_arm(tr, scores[4], tr_dead)}"
            f" \u2500\u2500\u2524"
        ),
        "                \u2502",
        (
            f"   {_arm(left, scores[3], left_dead)}"
            f" \u2500\u2500\u253c\u2500\u2500 "
            f"{_arm(right, scores[1], right_dead)}"
        ),
        "                \u2502",
        (
            f"   {_arm(bl, scores[5], bl_dead)}"
            f" \u2500\u2500\u2524"
        ),
        "                \u2502",
        f"              {_arm(bottom, scores[2], bottom_dead)}",
        "",
    ]

    console.print(
        Panel(
            "\n".join(lines),
            title="[bold]🎯 Skill Radar[/bold]",
            border_style="magenta",
        )
    )


def _print_monthly_chart_animated(
    monthly_breakdown: dict,
) -> None:
    """Print Section 2: Monthly AI ratio with animated bars.

    Each month's bar "fills in" left to right with a tiny delay.

    Args:
        monthly_breakdown: Dict of "YYYY-MM" → {human, ai, uncertain}.
    """
    sorted_months = sorted(monthly_breakdown.keys())
    valid_months: list[tuple[str, int, str]] = []

    for month in sorted_months:
        counts = monthly_breakdown[month]
        if not isinstance(counts, dict):
            continue
        human = counts.get("human", 0)
        total = (
            human
            + counts.get("ai", 0)
            + counts.get("uncertain", 0)
        )
        if total == 0:
            continue

        ratio = human / total
        pct = int(ratio * 100)

        if ratio >= 0.70:
            color = "green"
        elif ratio >= 0.50:
            color = "yellow"
        else:
            color = "red"

        valid_months.append((month, pct, color))

    if not valid_months:
        return

    console.print(
        Panel(
            "",
            title=(
                "[bold]📈 Monthly Human vs AI Ratio"
                "[/bold]"
            ),
            border_style="blue",
        )
    )

    # Clear panel and animate each bar
    for month, pct, color in valid_months:
        bar_max = 24
        filled = int(pct / 100 * bar_max)

        # Animate the bar filling
        for step in range(1, filled + 1):
            empty = bar_max - step
            bar = "█" * step + "░" * empty
            line = (
                f"\r  {month}  [{color}]{bar}"
                f"[/{color}]  {pct}% human"
            )
            console.print(line, end="")
            time.sleep(0.02)

        # Final line with declining marker
        suffix = ""
        if pct < 55:
            suffix = "  [red]← declining[/red]"
        console.print(
            f"\r  {month}  [{color}]{'█' * filled}"
            f"{'░' * (bar_max - filled)}[/{color}]"
            f"  {pct}% human{suffix}"
        )

    console.print()


def _print_dead_zones_flash(
    skill_profile: dict, dead_zones: list[str],
) -> None:
    """Print Section 3: Dead Zones with a flash effect.

    Prints the panel, clears it, then reprints with red border
    to create a "blink" effect.

    Args:
        skill_profile: Skill name → data dict.
        dead_zones: List of dead zone skill names.
    """
    if not dead_zones:
        console.print(
            Panel(
                "[green]No skills to revisit! "
                "All skills are actively exercised.[/green]",
                title="🎯 Skills to Revisit",
                border_style="green",
            )
        )
        return

    now = datetime.now(UTC)
    body_lines = [
        "[bold]Skills ready for a workout "
        "(45+ days):[/bold]\n",
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
            days_val = (now - ls).days
            ago = f"last used: {days_val} days ago"
        body_lines.append(
            f"  [red]•[/red]  {emoji} {skill_name} ({ago})"
        )

    body = "\n".join(body_lines)

    # Flash effect: dim → bright red
    dim_panel = Panel(
        body, title="🎯 Skills to Revisit", border_style="dim",
    )
    with Live(dim_panel, console=console, transient=True):
        time.sleep(0.15)

    console.print(
        Panel(
            body,
            title="[bold red]🎯 Skills to Revisit[/bold red]",
            border_style="bright_red",
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
            title="🧬 Your Coding Fingerprint",
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
        badge = (
            " ⚠️ NEEDS PRACTICE" if name in dead_zones else ""
        )
        lines.append(
            f"| {name} | {score:.1f}{badge} | {ls_str} |"
        )

    if dead_zones:
        lines.append("\n## Skills to Revisit\n")
        for name in dead_zones:
            data = skill_profile.get(name, {})
            ls = data.get("last_seen")
            if ls is None:
                ago = "ready for a workout"
            else:
                if ls.tzinfo is None:
                    ls = ls.replace(tzinfo=UTC)
                d = (now - ls).days
                ago = f"{d} days ago"
            lines.append(f"- **{name}** — {ago}")

    if coding_dna:
        lines.append("\n## Coding Fingerprint\n")
        lines.append(
            "- Primary language: "
            f"{coding_dna.get('primary_language', '?')}"
        )
        lines.append(
            "- Coding style: "
            f"{coding_dna.get('coding_style', '?')}"
        )
        lines.append(
            f"- AI ratio: {coding_dna.get('ai_ratio', 0):.1%}"
        )
        top = coding_dna.get("top_skills", [])
        if top:
            lines.append(
                f"- Top skills: {', '.join(top)}"
            )

    lines.append(
        "\n---\n*Generated by [atrophy]"
        "(https://github.com/atrophy/atrophy)*\n"
    )

    report_path = Path.cwd() / "report.md"
    report_path.write_text(
        "\n".join(lines), encoding="utf-8",
    )
    show_success(
        f"Report saved to [cyan]{report_path}[/cyan]"
    )


# ── COMMAND: atrophy challenge ──────────────────────────────────────


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
    show_banner()
    try:
        asyncio.run(_run_challenge(generate, done))
    except AtrophyError as exc:
        show_error(str(exc))
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
        show_error(
            "No project found.",
            hint="Run `atrophy init` first.",
        )
        raise typer.Exit(code=1)

    # ── Handle --done ───────────────────────────────────────────
    if done is not None:
        try:
            await storage.mark_challenge_complete(done)
        except AtrophyError as exc:
            await storage.close()
            show_error(str(exc))
            raise typer.Exit(code=1) from exc

        streak = await storage.get_streak(project.id)
        msg_lines = [
            f"Challenge #{done} marked complete!",
            f"Current streak: {streak} weeks",
        ]
        if streak >= 7:
            msg_lines.append(
                "\n🔥 On fire! You're unstoppable!"
            )

        show_success("\n".join(msg_lines))

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
            show_error(
                "No scan data found.",
                hint="Run `atrophy scan` first.",
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
            show_error(
                "No LLM provider configured.",
                hint="Run `atrophy config` to set one up.",
            )
            raise typer.Exit(code=1) from None

        # Load coding DNA
        dna_raw = await storage.get_setting("coding_dna")
        coding_dna = json.loads(dna_raw) if dna_raw else {}

        language = coding_dna.get("primary_language", "python")
        top_skills = coding_dna.get("top_skills", [])
        top_skill = top_skills[0] if top_skills else "general_programming"

        console.print()
        show_info(
            "🧠 AI Challenge Engine",
            "Generating personalised challenges…",
        )

        scanner = GitScanner(
            cwd, days_back=180, author_email=project.author_email
        )
        commits = scanner.scan_commits()

        mapper = SkillMapper()
        dead_zones = mapper.get_dead_zones(skill_profile)

        engine = ChallengeEngine(provider)

        new_challenges = await engine.generate_challenges(
            dead_zones=dead_zones,
            language=language,
            repo_path=Path(cwd),
            commits=commits,
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
    show_banner()
    from atrophy.tui.dashboard import AtrophyDashboard

    app_instance = AtrophyDashboard()
    app_instance.run()


@app.command()
def config() -> None:
    """Configure your LLM provider and model."""
    show_banner()

    from atrophy.cli.onboarding import _configure_provider

    settings = get_settings()
    current = settings.llm_provider

    console.print(
        Panel(
            f"Current provider: [bold cyan]{current}[/bold cyan]",
            title="[bold]⚙️  Configuration[/bold]",
            border_style="blue",
        )
    )
    console.print()

    _configure_provider()

    # Reload and show updated
    updated = get_settings()
    show_success(
        f"Provider set to "
        f"[bold]{updated.llm_provider}[/bold]"
    )


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
            show_error("Output file must have a .png extension.")
            raise typer.Exit(code=1)

        # Ensure it writes into the current working directory hierarchy
        if not safe_output.is_relative_to(cwd):
            show_error(
                "Security Check Failed: Output path must "
                "be within the current working directory."
            )
            raise typer.Exit(code=1)

        asyncio.run(_run_share(safe_output))
    except AtrophyError as exc:
        show_error(str(exc))
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
        show_error(
            "No project found.",
            hint="Run `atrophy init` first.",
        )
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

    show_success(f"Saved {safe_output} \u2014 share it on Twitter/X!")

@app.command()
def digest(
    open_editor: Annotated[
        bool,
        typer.Option(
            "--open",
            help="Open the digest in your $EDITOR",
        ),
    ] = False,
) -> None:
    """Generate a Weekly Digest aimed at journaling apps."""
    show_banner()
    try:
        asyncio.run(_run_digest(open_editor))
    except AtrophyError as exc:
        show_error(str(exc))
        raise typer.Exit(code=1) from exc

async def _run_digest(open_editor: bool) -> None:
    cwd = str(Path.cwd().resolve())
    storage = _get_storage()
    await storage.init_db()

    project = await storage.get_project(cwd)
    if not project:
        await storage.close()
        show_error("No project found.", hint="Run `atrophy init` first.")
        raise typer.Exit(code=1)

    # get data
    snapshots = await storage.get_all_skills_latest(project.id)
    pending = await storage.get_pending_challenges(project.id)
    import datetime as dt_mod
    wins = []
    if hasattr(storage, "get_recent_wins"):
        wins = await storage.get_recent_wins(project.id)
    else:
        # fetch directly via pure sqlalchemy logic
        from sqlalchemy import select
        from atrophy.core.storage import Win
        try:
            async with storage._session_factory() as session:
                result = await session.execute(
                    select(Win).where(Win.project_id == project.id, Win.date == dt_mod.date.today())
                )
                wins = list(result.scalars().all())
        except Exception:
            wins = []
            
    await storage.close()

    now = datetime.now(UTC)
    week_str = now.strftime("%Y-%W")
    
    settings = get_settings()
    digests_dir = Path(settings.data_dir) / "digests"
    digests_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"{week_str}.md"
    digest_path = digests_dir / filename
    
    lines = [
        f"## atrophy Weekly Digest \u2014 Week of {now.strftime('%B %-d, %Y')}",
        "",
        "### What I built this week",
        "- Human-written commits recorded this week",
    ]
    
    sk_names = [s.skill_name for s in snapshots if s.score > 10][:5]
    if sk_names:
        lines.append(f"- Skills exercised: {', '.join(sk_names)}")
    
    lines.append("")
    lines.append("### Growth this week")
    if wins:
        for w in wins:
            lines.append(f"- {w.message}")
    else:
        lines.append("- Consistent practice and maintenance.")
        
    lines.append("")
    lines.append("### Focus for next week")
    # find the most decayed skill
    if snapshots:
        snapshots.sort(key=lambda s: s.score)
        worst = snapshots[0]
        ago = "never"
        if worst.last_seen:
            dt = worst.last_seen.replace(tzinfo=UTC) if worst.last_seen.tzinfo is None else worst.last_seen
            ago = f"{(now - dt).days} days since last used"
        lines.append(f"Top recommendation: {worst.skill_name} ({ago})")
    else:
        lines.append("Keep building!")
        
    lines.append("")
    lines.append("### Pending challenges")
    if pending:
        for c in pending:
            d_color = "🟢" if c.difficulty == "easy" else ("🟡" if c.difficulty == "medium" else "🔴")
            lines.append(f"- {d_color} [{c.difficulty.title()}] {c.title} (~{c.estimated_minutes} min)")
    else:
        lines.append("- All clear!")
        
    digest_path.write_text("\n".join(lines), encoding="utf-8")
    
    console.print(f"[green]Digest saved. Open with: cat {digest_path}[/green]")
    if not open_editor:
        console.print("[dim]Tip: Run `atrophy digest --open` to open in your $EDITOR[/dim]")
    else:
        import os, subprocess
        editor = os.environ.get("EDITOR", "notepad")
        subprocess.run([editor, str(digest_path)], shell=False, timeout=30)

