"""Centralized terminal output helpers for atrophy.

Provides styled Rich panels, an animated startup banner,
and helper functions used across all CLI commands.
Never use bare ``print()`` — everything goes through these.
"""

from __future__ import annotations

import time

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

console = Console()


# ── Startup Banner ──────────────────────────────────────────────────


def show_banner() -> None:
    """Show a 0.5-second animated startup banner.

    Frame 1 (dim): ``🧬 atrophy``
    Frame 2 (gradient): full tagline with purple→blue gradient.
    Uses Rich Live with transient=True so it disappears after.
    """
    frame1 = Text()
    frame1.append("  🧬 ", style="dim")
    frame1.append("a t r o p h y", style="dim magenta")

    frame2 = Text()
    frame2.append("  🧬 ", style="bold")
    # Purple → blue gradient via manually styled characters
    tagline = "atrophy"
    gradient_styles = [
        "bold #9b59b6",  # purple
        "bold #8e44ad",
        "bold #7d3c98",
        "bold #6c3483",
        "bold #5b2c6f",
        "bold #4a69bd",  # transition
        "bold #3498db",  # blue
    ]
    for i, ch in enumerate(tagline):
        style = gradient_styles[i % len(gradient_styles)]
        frame2.append(ch, style=style)
    frame2.append(
        " — your coding skills have a half-life",
        style="italic #8b949e",
    )

    with Live(frame1, console=console, transient=True):
        time.sleep(0.3)

    with Live(frame2, console=console, transient=True):
        time.sleep(0.2)


# ── Styled Output Panels ───────────────────────────────────────────


def show_error(message: str, hint: str = "") -> None:
    """Print an error message in a styled red panel.

    Args:
        message: The error text to display.
        hint: Optional helpful hint text shown dimmed below.
    """
    body = f"[red]{message}[/red]"
    if hint:
        body += f"\n\n[dim]{hint}[/dim]"
    console.print(
        Panel(
            body,
            title="[bold red]❌ Error[/bold red]",
            border_style="red",
        )
    )


def show_success(message: str) -> None:
    """Print a success message in a styled green panel.

    Args:
        message: The success text to display.
    """
    console.print(
        Panel(
            f"[green]{message}[/green]",
            title="[bold green]✅ Done[/bold green]",
            border_style="green",
        )
    )


def show_info(title: str, message: str) -> None:
    """Print an info message in a styled blue panel.

    Args:
        title: Panel title text.
        message: The info body text.
    """
    console.print(
        Panel(
            message,
            title=f"[bold blue]{title}[/bold blue]",
            border_style="blue",
        )
    )


def show_warning(message: str) -> None:
    """Print a warning message in a styled yellow panel.

    Args:
        message: The warning text to display.
    """
    console.print(
        Panel(
            f"[yellow]{message}[/yellow]",
            title="[bold yellow]⚠ Warning[/bold yellow]",
            border_style="yellow",
        )
    )
