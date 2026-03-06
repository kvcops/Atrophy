"""Textual-based interactive dashboard for atrophy.

Displays skill decay charts, AI vs human commit ratios,
and active challenges in a terminal UI.
"""

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rich.table import Table
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Static

from atrophy import __version__
from atrophy.config import get_settings
from atrophy.core.skill_mapper import SKILL_PATTERNS
from atrophy.core.storage import Storage


class HeaderBar(Horizontal):
    """Row 1: Header bar."""

    def compose(self) -> ComposeResult:
        yield Label("🧬 [bold purple]atrophy[/bold purple]", id="header-left")
        yield Label("Loading project...", id="header-center")
        yield Label("Loading stats...", id="header-right")


class SkillScoresPanel(Vertical):
    """Row 2 Left (60%): Skill Scores panel."""

    def compose(self) -> ComposeResult:
        yield Label("Your Skill Muscle Memory", classes="panel-title")
        yield Static("Loading skills...", id="skills-table")


class AIRatioTimeline(Vertical):
    """Row 2 Right (40%): AI Ratio Timeline."""

    def compose(self) -> ComposeResult:
        yield Label("Skill Exercise Rate Over Time", classes="panel-title")
        yield Static("Loading timeline...", id="timeline-chart")


class ChallengeCard(Vertical):
    """A compact card representing a pending challenge."""

    def __init__(self, challenge):
        super().__init__()
        self.challenge = challenge
        self.classes = "challenge-card"

    def compose(self) -> ComposeResult:
        c = self.challenge
        diff_color = (
            "green"
            if c.difficulty == "easy"
            else ("yellow" if c.difficulty == "medium" else "red")
        )
        emoji = SKILL_PATTERNS.get(c.skill_name, {}).get("emoji", "🧩")
        time_est = {"easy": "15m", "medium": "30m", "hard": "60m"}.get(
            c.difficulty.lower(), "30m"
        )

        yield Label(
            f"[{diff_color}]{c.difficulty.upper()}[/{diff_color}] "
            f"| {emoji} {c.title} | {time_est}"
        )
        yield Label(f"Skill: {c.skill_name}", classes="dim")
        yield Button("Done", id=f"complete_{c.id}", variant="primary")


class ChallengesPanel(Vertical):
    """Row 3: Challenges panel."""

    def compose(self) -> ComposeResult:
        yield Label("Pending Challenges", classes="panel-title")
        yield Horizontal(id="challenges-container")


class DashboardFooter(Horizontal):
    """Row 4: Footer."""

    def compose(self) -> ComposeResult:
        yield Label(
            f"[Q] Quit  [R] Refresh  [C] View All Challenges  atrophy v{__version__}"
        )


class AtrophyDashboard(App):
    """Textual app for the primary dashboard."""

    CSS = """
    Screen {
        background: #0d1117;
    }
    .header { background: #161b22; height: 3; }
    .score-green { color: #3fb950; }
    .score-yellow { color: #d29922; }
    .score-red { color: #f85149; }
    .dead-zone { border: solid #f85149; }
    .skill-card { background: #161b22; border: solid #30363d; margin: 1; padding: 1; }
    .challenge-card {
        background: #161b22; border: solid #388bfd; margin: 1; padding: 1;
        min-width: 40; height: auto;
    }
    .panel-title { color: #58a6ff; text-style: bold; margin-bottom: 1; }

    HeaderBar {
        height: 3;
        background: #161b22;
        layout: horizontal;
        padding-top: 1;
        padding-left: 1;
        padding-right: 1;
    }
    #header-left { width: 1fr; content-align: left middle; }
    #header-center { width: 1fr; content-align: center middle; }
    #header-right { width: 1fr; content-align: right middle; }

    #row-2 {
        height: 1fr;
        layout: horizontal;
        margin: 1 1 0 1;
    }

    SkillScoresPanel {
        width: 60%;
        border: solid #30363d;
        background: #161b22;
        padding: 1;
        margin-right: 1;
    }

    AIRatioTimeline {
        width: 40%;
        border: solid #30363d;
        background: #161b22;
        padding: 1;
    }

    ChallengesPanel {
        height: 12;
        border: solid #30363d;
        background: #161b22;
        padding: 1;
        margin: 1;
    }

    #challenges-container {
        height: auto;
        overflow-x: auto;
        overflow-y: hidden;
    }

    DashboardFooter {
        height: 3;
        background: #161b22;
        content-align: center middle;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "challenges", "Challenges"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the layout."""
        yield HeaderBar()
        yield Horizontal(SkillScoresPanel(), AIRatioTimeline(), id="row-2")
        yield ChallengesPanel()
        yield DashboardFooter()

    def on_mount(self) -> None:
        """Lifecycle point to trigger data loading."""
        self.load_dashboard_data()

    @work(exclusive=True)
    async def load_dashboard_data(self) -> None:
        """Load data async and schedule UI updates."""
        settings = get_settings()
        cwd = str(Path.cwd().resolve())
        storage = Storage(settings.db_path)
        await storage.init_db()

        project = await storage.get_project(cwd)
        if not project:
            await storage.close()
            self._update_header_center("No project", "Never")
            self._no_project_found()
            return

        snapshots = await storage.get_all_skills_latest(project.id)

        monthly_raw = await storage.get_setting("monthly_breakdown")
        monthly_breakdown = json.loads(monthly_raw) if monthly_raw else {}

        if not monthly_breakdown:
            dna_raw = await storage.get_setting("coding_dna")
            coding_dna = json.loads(dna_raw) if dna_raw else {}
            monthly_breakdown = coding_dna.get("monthly_breakdown", {})

        streak = await storage.get_streak(project.id)
        pending_challenges = await storage.get_pending_challenges(project.id)

        await storage.close()

        # Update Header
        scan_time_str = "Never"
        if project.last_scanned_at:
            dt = project.last_scanned_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            scan_time_str = dt.strftime("%Y-%m-%d %H:%M")

        self._update_header_center(project.name, scan_time_str)

        total_h = 0
        total_all = 0
        for counts in monthly_breakdown.values():
            if isinstance(counts, dict):
                h = counts.get("human", 0)
                a = counts.get("ai", 0)
                u = counts.get("uncertain", 0)
                total_h += h
                total_all += h + a + u

        h_pct = int(total_h / total_all * 100) if total_all > 0 else 0
        pct_color = (
            "score-green"
            if h_pct >= 70
            else ("score-yellow" if h_pct >= 50 else "score-red")
        )

        header_right_text = (
            f"Skill Exercise Rate: [{pct_color}]{h_pct}%[/{pct_color}]"
            f"   🔥 {streak}-week streak"
        )
        self._update_header_right(header_right_text)

        # Update body
        self._update_skills_table(snapshots)
        self._update_timeline(monthly_breakdown)
        self._update_challenges(pending_challenges)

    def _no_project_found(self) -> None:
        """Handle case when no project is initialized."""
        self.query_one("#skills-table", Static).update("Run `atrophy init` first.")
        self.query_one("#timeline-chart", Static).update("N/A")

    def _update_header_center(self, project_name: str, scan_time_str: str) -> None:
        self.query_one("#header-center", Label).update(
            f"[cyan]{project_name}[/cyan] | Last scanned: {scan_time_str}"
        )

    def _update_header_right(self, text: str) -> None:
        self.query_one("#header-right", Label).update(text)

    def _update_skills_table(self, snapshots) -> None:
        """Render a Rich-style table into the Static widget."""
        table = Table(show_header=True, show_edge=False, box=None)
        table.add_column("Emoji")
        table.add_column("Skill Name", style="cyan")
        table.add_column("Score Bar", min_width=20)
        table.add_column("Last Used")
        table.add_column("Trend")

        skill_profile = {}
        for snap in snapshots:
            pattern = SKILL_PATTERNS.get(snap.skill_name, {})
            skill_profile[snap.skill_name] = {
                "score": snap.score,
                "last_seen": snap.last_seen,
                "emoji": pattern.get("emoji", "🧩"),
            }

        now = datetime.now(UTC)
        cutoff = now - timedelta(days=45)
        has_dead_zone = False

        sorted_skills = sorted(
            skill_profile.items(), key=lambda x: x[1]["score"], reverse=True
        )

        for name, data in sorted_skills:
            score = data["score"]
            emoji = data["emoji"]
            last_seen = data["last_seen"]

            if score >= 60:
                score_style = "green"
            elif score >= 30:
                score_style = "yellow"
            else:
                score_style = "red"

            bar_filled = int(score / 5)
            bar_empty = 20 - bar_filled
            bar = Text()
            bar.append("█" * bar_filled, style=score_style)
            bar.append("░" * bar_empty, style="dim")

            is_dead_zone = False
            if last_seen is None or score < 8:
                is_dead_zone = True
            elif last_seen.tzinfo is None and last_seen.replace(tzinfo=UTC) < cutoff:
                is_dead_zone = True
            elif last_seen.tzinfo is not None and last_seen < cutoff:
                is_dead_zone = True

            if is_dead_zone:
                status = Text("⚡ Needs Practice", style="bold red")
                has_dead_zone = True
            else:
                status = Text("—", style="dim")

            if last_seen is None:
                last_text = Text("never", style="red")
            else:
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=UTC)
                days_ago = (now - last_seen).days
                if days_ago == 0:
                    last_text = Text("today", style="green")
                elif days_ago <= 30:
                    last_text = Text(f"{days_ago}d ago", style="green")
                else:
                    last_text = Text(f"{days_ago}d ago", style="red")

            table.add_row(emoji, name, bar, last_text, status)

        panel = self.query_one("SkillScoresPanel")
        if has_dead_zone:
            panel.add_class("dead-zone")
        else:
            panel.remove_class("dead-zone")

        self.query_one("#skills-table", Static).update(table)

    def _update_timeline(self, monthly_breakdown: dict) -> None:
        """Render the last 6 months as ASCII bar chart."""
        lines = []
        months = sorted(monthly_breakdown.keys())[-6:]

        for month in months:
            counts = monthly_breakdown[month]
            if not isinstance(counts, dict):
                continue
            h = counts.get("human", 0)
            a = counts.get("ai", 0)
            u = counts.get("uncertain", 0)
            tot = h + a + u
            if tot == 0:
                continue

            ratio = h / tot
            pct = int(ratio * 100)

            bar_len = 16
            filled = int(ratio * bar_len)
            empty = bar_len - filled

            color = "green" if ratio >= 0.7 else ("yellow" if ratio >= 0.4 else "red")
            bar = (
                f"[{color}]"
                + "█" * filled
                + "[/"
                + color
                + "]"
                + "[dim]"
                + "░" * empty
                + "[/dim]"
            )

            trend = " [red]←[/red]" if ratio < 0.55 else ""
            lines.append(f"{month} {bar} {pct}%{trend}")

        if not lines:
            self.query_one("#timeline-chart", Static).update(
                "[dim]No timeline data...[/dim]"
            )
        else:
            self.query_one("#timeline-chart", Static).update("\n".join(lines))

    def _update_challenges(self, pending_challenges) -> None:
        """Add cards to the challenges horizontal layout."""
        container = self.query_one("#challenges-container", Horizontal)
        for child in container.children:
            child.remove()

        if not pending_challenges:
            container.mount(
                Label(
                    "[dim]No pending challenges. "
                    "Run `atrophy challenge generate`.[/dim]"
                )
            )
            return

        for c in pending_challenges[
            :5
        ]:  # Display up to 5 so we don't overflow completely
            container.mount(ChallengeCard(c))

    def action_refresh(self) -> None:
        """Handle the 'refresh' binding."""
        self.load_dashboard_data()

    def action_challenges(self) -> None:
        """Handle the 'challenges' binding - print help or switch screen."""
        pass


def serve_dashboard():
    """Serves the dashboard to a browser on localhost:8000 via Textual."""
    # SECURITY: use shell=False, provide timeout= None to let it run indefinitely.
    # We must use timeout though based on the rules. We will set it to 3600*24.
    try:
        subprocess.run(  # noqa: S603
            ["textual", "serve", __file__],  # noqa: S607
            shell=False,
            timeout=86400,
        )
    except subprocess.TimeoutExpired:
        pass
    except KeyboardInterrupt:
        pass
