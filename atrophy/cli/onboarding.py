"""Onboarding flow for new atrophy users.

Displays a beautiful Rich welcome panel, explains what atrophy does,
and optionally configures an LLM provider for challenge generation.

Security:
    - API keys are collected via getpass (never echoed to the terminal).
    - Keys are set as environment variables only — never written to disk.
    - Provider choice is saved to ~/.atrophy/config.json (keys excluded).
"""

import getpass
import os

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from atrophy.config import get_settings

console = Console()


def run_onboarding() -> None:
    """Run the interactive onboarding wizard.

    Displays a welcome banner, explains atrophy, and optionally
    configures an LLM provider for challenge generation.
    """
    _print_welcome()
    _configure_provider()


def _print_welcome() -> None:
    """Print the welcome banner and feature overview."""
    title = Text()
    title.append("  a t r o p h y  ", style="bold magenta")
    title.append("\n")
    title.append(
        "  Your coding skills have a half-life. Let's measure it.",
        style="dim italic",
    )

    features = (
        "\n"
        "[bold cyan]What atrophy does:[/bold cyan]\n\n"
        "  [green]•[/green]  Scans your git history and statistically"
        " separates human-written code from AI-generated code\n"
        "  [green]•[/green]  Maps your human commits to 10 coding"
        " skill categories and tracks which are decaying\n"
        "  [green]•[/green]  Generates personalised coding challenges"
        " to exercise your weakest skills\n"
    )

    console.print()
    console.print(
        Panel(
            title,
            border_style="magenta",
            padding=(1, 4),
        )
    )
    console.print(features)


def _configure_provider() -> None:
    """Ask the user to pick an LLM provider for challenge generation."""
    console.print(
        "[bold]Which LLM provider for challenges?[/bold] "
        "(Enter to skip)\n"
    )

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", width=4)
    table.add_column()
    table.add_row("1)", "OpenAI  (gpt-4o-mini)")
    table.add_row("2)", "Anthropic  (claude-haiku-4-5)")
    table.add_row("3)", "Ollama  (free, local)")
    table.add_row("4)", "Skip  (configure later)")
    console.print(table)
    console.print()

    choice = console.input("[dim]Choice [1/2/3/4]:[/dim] ").strip()

    settings = get_settings()

    match choice:
        case "1":
            _set_openai_key(settings)
        case "2":
            _set_anthropic_key(settings)
        case "3":
            settings.llm_provider = "ollama"
            settings.save()
            console.print(
                "\n[green]✓[/green] Ollama selected. "
                "Make sure Ollama is running: [cyan]ollama serve[/cyan]"
            )
        case _:
            settings.llm_provider = "none"
            settings.save()
            console.print(
                "\n[dim]Skipped — you can configure a provider "
                "anytime with:[/dim] [cyan]atrophy config[/cyan]"
            )
            return

    console.print(
        "\n[dim]You can change this anytime with:[/dim] "
        "[cyan]atrophy config[/cyan]\n"
    )


def _set_openai_key(settings) -> None:
    """Prompt for OpenAI API key via getpass (never echoed).

    SECURITY: Key is set as an environment variable only — it is
    never written to the config file on disk.

    Args:
        settings: The Settings instance to update.
    """
    console.print(
        "\n[dim]Paste your OpenAI API key "
        "(input is hidden):[/dim]"
    )
    key = getpass.getpass("  API Key: ")
    if not key.strip():
        console.print("[yellow]No key entered — skipping.[/yellow]")
        return

    # Set as env var so pydantic-settings picks it up
    os.environ["ATROPHY_OPENAI_API_KEY"] = key.strip()
    settings.llm_provider = "openai"
    settings.save()
    console.print("[green]✓[/green] OpenAI configured.")


def _set_anthropic_key(settings) -> None:
    """Prompt for Anthropic API key via getpass (never echoed).

    SECURITY: Key is set as an environment variable only — it is
    never written to the config file on disk.

    Args:
        settings: The Settings instance to update.
    """
    console.print(
        "\n[dim]Paste your Anthropic API key "
        "(input is hidden):[/dim]"
    )
    key = getpass.getpass("  API Key: ")
    if not key.strip():
        console.print("[yellow]No key entered — skipping.[/yellow]")
        return

    os.environ["ATROPHY_ANTHROPIC_API_KEY"] = key.strip()
    settings.llm_provider = "anthropic"
    settings.save()
    console.print("[green]✓[/green] Anthropic configured.")
