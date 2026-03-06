"""atrophy CLI — Typer application with all top-level commands."""

import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from atrophy import __version__

# Force UTF-8 output on Windows to avoid cp1252 encoding errors with
# Rich markup and special characters.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

console = Console()

app = typer.Typer(
    name="atrophy",
    help="Your coding skills have a half-life. atrophy measures it.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


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


@app.command()
def init(
    path: Annotated[
        str,
        typer.Argument(
            help="Path to the git repository to track.",
        ),
    ] = ".",
) -> None:
    """Initialize atrophy tracking for a git repository."""
    console.print(
        Panel(
            "[bold yellow]Coming soon:[/bold yellow] init\n\n"
            f"Will initialize atrophy tracking for: [cyan]{path}[/cyan]",
            title="[yellow]>> Under Construction[/yellow]",
            border_style="yellow",
        )
    )


@app.command()
def scan(
    days: Annotated[
        int,
        typer.Option(
            "--days",
            "-d",
            help="Number of days of history to scan.",
            min=1,
            max=365,
        ),
    ] = 90,
) -> None:
    """Scan git history and analyze commits for AI patterns."""
    console.print(
        Panel(
            "[bold yellow]Coming soon:[/bold yellow] scan\n\n"
            f"Will scan the last [cyan]{days}[/cyan] days of git history.",
            title="[yellow]>> Under Construction[/yellow]",
            border_style="yellow",
        )
    )


@app.command()
def report() -> None:
    """Generate a skill atrophy report."""
    console.print(
        Panel(
            "[bold yellow]Coming soon:[/bold yellow] report\n\n"
            "Will generate a comprehensive skill atrophy report.",
            title="[yellow]>> Under Construction[/yellow]",
            border_style="yellow",
        )
    )


@app.command()
def challenge() -> None:
    """Get a coding challenge to exercise a decaying skill."""
    console.print(
        Panel(
            "[bold yellow]Coming soon:[/bold yellow] challenge\n\n"
            "Will generate a targeted coding challenge for your weakest skill.",
            title="[yellow]>> Under Construction[/yellow]",
            border_style="yellow",
        )
    )


@app.command()
def dashboard() -> None:
    """Launch the interactive TUI dashboard."""
    console.print(
        Panel(
            "[bold yellow]Coming soon:[/bold yellow] dashboard\n\n"
            "Will launch the Textual-based interactive dashboard.",
            title="[yellow]>> Under Construction[/yellow]",
            border_style="yellow",
        )
    )
