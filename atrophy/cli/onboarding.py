"""Onboarding flow for new atrophy users.

Displays a beautiful Rich welcome panel, explains what atrophy does,
and optionally configures an LLM provider for challenge generation.

Security:
    - API keys are collected via getpass (never echoed to the terminal).
    - Keys are saved to ~/.atrophy/.env (never in config.json).
    - Provider choice is saved to ~/.atrophy/config.json (keys excluded).
"""

from __future__ import annotations

import asyncio
import getpass

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from atrophy.config import get_settings
from atrophy.exceptions import ProviderError

console = Console()


def run_onboarding() -> None:
    """Run the interactive onboarding wizard.

    Displays a welcome banner, explains atrophy, and optionally
    configures an LLM provider for challenge generation.
    """
    _print_welcome()
    _configure_provider()

    # Show calibration message based on scan_count
    import asyncio
    from atrophy.core.storage import Storage
    settings = get_settings()
    storage = Storage(settings.db_path)
    asyncio.run(storage.init_db())
    try:
        scan_count_str = asyncio.run(storage.get_setting("scan_count", "0"))
        scan_count = int(scan_count_str)
    except Exception:
        scan_count = 0
    finally:
        asyncio.run(storage.close())

    if scan_count < 3:
        console.print(
            Panel(
                "[dim]atrophy needs 2-3 scans over a few weeks to calibrate "
                "your personal baseline. Your first report may show lower scores "
                "than reality — that's normal.[/dim]\n\n"
                "[dim]The tool gets smarter about YOU over time.\n"
                "Run [bold]atrophy scan[/bold] weekly for the best results.[/dim]",
                title="📊 About your first scan",
                border_style="yellow",
                expand=False,
            )
        )
    else:
        console.print(
            Panel(
                "📈 [green]atrophy is now calibrated to your coding style.[/green]",
                border_style="green",
                expand=False,
            )
        )


# ── Welcome ─────────────────────────────────────────────────────


def _print_welcome() -> None:
    """Print the welcome banner and feature overview."""
    console.print(
        Panel(
            "[bold purple]🧬 atrophy[/bold purple]\n"
            "[dim]Your coding skills have a half-life. "
            "atrophy measures it.[/dim]\n\n"
            "• Analyzes your git history to map skill health\n"
            "• Separates human-written commits from "
            "AI-assisted ones\n"
            "• Generates weekly challenges for your "
            "decaying skills",
            border_style="purple",
        )
    )


# ── Provider picker ─────────────────────────────────────────────


def _configure_provider() -> None:
    """Two-level interactive flow: pick a provider, then a model."""
    table = Table(
        title="Choose Your AI Provider",
        title_style="bold blue",
        border_style="blue",
        show_lines=True,
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Provider", style="bold", width=12)
    table.add_column("Best for")
    table.add_column("Cost", style="green", width=22)

    table.add_row(
        "1",
        "OpenAI",
        "GPT-4o-mini, o4-mini, GPT-5.x",
        "Pay per token",
    )
    table.add_row(
        "2",
        "Anthropic",
        "Claude Haiku, Sonnet, Opus",
        "Pay per token",
    )
    table.add_row(
        "3",
        "OpenRouter",
        "500+ models, free options available",
        "Free tier + pay per token",
    )
    table.add_row(
        "4",
        "Ollama",
        "Local models or ollama.com cloud",
        "Free (local) / key (cloud)",
    )
    table.add_row(
        "5",
        "Skip",
        "No challenges — set up later",
        "Free",
    )
    console.print(table)

    choice = typer.prompt("\nEnter number", default="5")

    match choice:
        case "1":
            _setup_openai()
        case "2":
            _setup_anthropic()
        case "3":
            _setup_openrouter()
        case "4":
            _setup_ollama()
        case _:
            _setup_skip()


# ── OpenAI ──────────────────────────────────────────────────────


def _setup_openai() -> None:
    """Level 2A: OpenAI model picker and key entry."""
    models = [
        (
            "gpt-4o-mini",
            "Fast, cheap, ideal for challenges",
            "$0.15/1M in",
        ),
        ("gpt-4o", "More capable", "$2.50/1M in"),
        ("o4-mini", "Reasoning model", "$1.10/1M in"),
    ]

    model_table = Table(
        border_style="cyan", title="OpenAI Models"
    )
    model_table.add_column("#", width=3)
    model_table.add_column("Model ID", style="cyan")
    model_table.add_column("Notes")
    model_table.add_column("Price", justify="right")
    for i, (mid, note, price) in enumerate(models, 1):
        model_table.add_row(str(i), mid, note, price)
    console.print(model_table)
    console.print(
        "[dim]Or type any OpenAI model ID directly[/dim]"
    )

    raw = typer.prompt("Model # or ID", default="1")
    if raw.isdigit() and 1 <= int(raw) <= len(models):
        model_id = models[int(raw) - 1][0]
    else:
        model_id = raw

    key = getpass.getpass(
        "Paste OpenAI API key (hidden, starts with sk-): "
    )
    if not key.strip():
        console.print(
            "[yellow]No key entered — skipping.[/yellow]"
        )
        return
    if not key.startswith("sk-"):
        console.print(
            "[yellow]⚠  Key doesn't look like OpenAI "
            "format (sk-...) — saved anyway[/yellow]"
        )

    _save_settings(
        llm_provider="openai", openai_model=model_id
    )
    _save_env_key("ATROPHY_OPENAI_API_KEY", key.strip())
    console.print("[green]✓ OpenAI configured![/green]")
    _print_key_reminder()


# ── Anthropic ───────────────────────────────────────────────────


def _setup_anthropic() -> None:
    """Level 2B: Anthropic model picker and key entry."""
    models = [
        (
            "claude-haiku-4-5-20251001",
            "Fastest, cheapest",
            "$0.80/1M in",
        ),
        (
            "claude-sonnet-4-6",
            "Balanced, recommended",
            "$3.00/1M in",
        ),
        (
            "claude-opus-4-6",
            "Most capable",
            "$15.00/1M in",
        ),
    ]

    model_table = Table(
        border_style="cyan", title="Anthropic Models"
    )
    model_table.add_column("#", width=3)
    model_table.add_column("Model ID", style="cyan")
    model_table.add_column("Notes")
    model_table.add_column("Price", justify="right")
    for i, (mid, note, price) in enumerate(models, 1):
        model_table.add_row(str(i), mid, note, price)
    console.print(model_table)
    console.print(
        "[dim]Or type any Anthropic model ID directly[/dim]"
    )

    raw = typer.prompt("Model # or ID", default="1")
    if raw.isdigit() and 1 <= int(raw) <= len(models):
        model_id = models[int(raw) - 1][0]
    else:
        model_id = raw

    key = getpass.getpass(
        "Paste Anthropic API key "
        "(hidden, starts with sk-ant-): "
    )
    if not key.strip():
        console.print(
            "[yellow]No key entered — skipping.[/yellow]"
        )
        return
    if not key.startswith("sk-ant-"):
        console.print(
            "[yellow]⚠  Key doesn't look like Anthropic "
            "format — saved anyway[/yellow]"
        )

    _save_settings(
        llm_provider="anthropic", anthropic_model=model_id
    )
    _save_env_key("ATROPHY_ANTHROPIC_API_KEY", key.strip())
    console.print("[green]✓ Anthropic configured![/green]")
    _print_key_reminder()


# ── OpenRouter ──────────────────────────────────────────────────


def _setup_openrouter() -> None:
    """Level 2C: OpenRouter — live model picker with search."""
    console.print(
        Panel(
            "OpenRouter gives you access to "
            "[bold]500+ models[/bold] with one API key.\n"
            "Free models (like Gemini Flash, Llama 3.3 70B) "
            "are available with no credits.\n\n"
            "Get your key at: "
            "[link=https://openrouter.ai/keys]"
            "https://openrouter.ai/keys[/link]",
            border_style="blue",
            title="OpenRouter",
        )
    )

    # Step 1: Get API key
    key = getpass.getpass(
        "Paste OpenRouter API key "
        "(hidden, starts with sk-or-): "
    )
    if not key.strip():
        console.print(
            "[yellow]No key entered — skipping.[/yellow]"
        )
        return
    if not key.startswith("sk-or-"):
        console.print(
            "[yellow]⚠  Key doesn't look like OpenRouter "
            "format (sk-or-...)[/yellow]"
        )
        if not typer.confirm("Continue anyway?", default=False):
            return

    # Step 2: Fetch live model list
    models: list[dict] = []
    with console.status(
        "[bold blue]Fetching models from openrouter.ai..."
        "[/bold blue]"
    ):
        try:
            from atrophy.providers.openrouter_provider import (
                OpenRouterProvider,
            )

            models = asyncio.run(
                OpenRouterProvider.fetch_models(key.strip())
            )
        except Exception as exc:
            console.print(
                f"[yellow]⚠  Could not fetch model list: "
                f"{exc}[/yellow]"
            )
            console.print(
                "[dim]You can paste any OpenRouter model ID "
                "directly instead.[/dim]"
            )

    display_list = models[:30] if models else []

    # Step 3: Show initial table
    if display_list:
        console.print(
            _render_model_table(
                display_list,
                f"Top Models (showing 30 of {len(models)})",
            )
        )
        console.print(
            "\n[dim]Commands:[/dim]\n"
            "  [cyan]number[/cyan]   → pick from list above\n"
            "  [cyan]search term[/cyan] → filter list "
            "(e.g. 'gemini', 'free', 'deepseek')\n"
            "  [cyan]model/id[/cyan]   → paste any model ID "
            "directly (e.g. google/gemini-flash-1.5)\n"
        )

    # Step 4: Interactive selection loop
    chosen_model: str | None = None
    while not chosen_model:
        raw = typer.prompt("Model # / search / ID")

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(display_list):
                chosen_model = display_list[idx]["id"]
            else:
                console.print(
                    f"[red]Number out of range. "
                    f"Enter 1-{len(display_list)}[/red]"
                )

        elif "/" in raw:
            # Direct model ID
            match = next(
                (m for m in models if m["id"] == raw), None
            )
            if match:
                chosen_model = raw
                console.print(
                    f"[green]✓ Found:[/green] {match['name']}"
                )
            else:
                console.print(
                    f"[yellow]'{raw}' not in fetched list "
                    "(may still be valid)[/yellow]"
                )
                if typer.confirm(
                    f"Use '{raw}' anyway?", default=True
                ):
                    chosen_model = raw

        else:
            # Search
            from atrophy.providers.openrouter_provider import (
                OpenRouterProvider,
            )

            filtered = OpenRouterProvider.search_models(
                models, raw
            )
            if not filtered:
                console.print(
                    f"[red]No models matching '{raw}'[/red]"
                )
            else:
                display_list = filtered[:20]
                console.print(
                    _render_model_table(
                        display_list,
                        f"Results for '{raw}' "
                        f"({len(filtered)} matches)",
                    )
                )

    # Step 5: Confirm
    console.print(
        f"\n[bold green]✓ Selected:[/bold green] "
        f"[cyan]{chosen_model}[/cyan]"
    )
    if typer.confirm("Confirm?", default=True):
        _save_settings(
            llm_provider="openrouter",
            openrouter_model=chosen_model,
        )
        _save_env_key(
            "ATROPHY_OPENROUTER_API_KEY", key.strip()
        )
        console.print(
            "[green]✓ OpenRouter configured![/green]"
        )
        _print_key_reminder()


def _render_model_table(
    model_list: list[dict],
    title: str = "OpenRouter Models",
) -> Table:
    """Build a Rich table of OpenRouter models.

    Args:
        model_list: List of model dicts from fetch_models().
        title: Table title.

    Returns:
        A Rich Table instance ready to print.
    """
    t = Table(
        title=title, border_style="blue", show_lines=False
    )
    t.add_column("#", width=4, style="dim")
    t.add_column("Model ID", style="cyan", no_wrap=True)
    t.add_column("Name", max_width=32)
    t.add_column("Context", justify="right", width=8)
    t.add_column("Price/1M", justify="right", width=12)
    for i, m in enumerate(model_list, 1):
        ctx = (
            f"{m['context_length'] // 1000}K"
            if m["context_length"] > 1000
            else "?"
        )
        price = (
            "[green]FREE 🎉[/green]"
            if m["is_free"]
            else f"${m['price_per_million']:.2f}"
        )
        t.add_row(str(i), m["id"], m["name"], ctx, price)
    return t


# ── Ollama ──────────────────────────────────────────────────────


def _setup_ollama() -> None:
    """Level 2D: Ollama local/cloud picker."""
    console.print(
        Panel(
            "  [cyan]1[/cyan]  [bold]Local[/bold]  — "
            "models on this machine "
            "(free, private, offline)\n"
            "  [cyan]2[/cyan]  [bold]Cloud[/bold]  — "
            "ollama.com API "
            "(larger models, needs account)",
            title="🦙 Ollama Mode",
            border_style="yellow",
        )
    )
    ollama_mode = typer.prompt("Enter 1 or 2", default="1")

    if ollama_mode == "1":
        _setup_ollama_local(ollama_mode)
    if ollama_mode == "2":
        _setup_ollama_cloud()


def _setup_ollama_local(
    ollama_mode: str,
) -> None:
    """Pick a local Ollama model.

    Args:
        ollama_mode: Mutable reference; set to "2" if user
            chooses to switch to cloud.
    """
    with console.status("Scanning for local Ollama models..."):
        from atrophy.providers.ollama_provider import (
            OllamaProvider,
        )

        local_models = asyncio.run(
            OllamaProvider.list_local_models()
        )

    if not local_models:
        console.print(
            Panel(
                "[yellow]No models found.[/yellow] "
                "Is Ollama running?\n\n"
                "Start Ollama:       "
                "[dim]ollama serve[/dim]\n"
                "Pull a model:       "
                "[dim]ollama pull llama3.2[/dim]"
                "        (~2 GB)\n"
                "                    "
                "[dim]ollama pull qwen2.5-coder:7b[/dim]"
                "  (~4 GB, code)\n"
                "                    "
                "[dim]ollama pull deepseek-r1:7b[/dim]"
                "    (~4 GB, reasoning)\n\n"
                "After pulling, run "
                "[bold]atrophy config[/bold] "
                "to complete setup.",
                title="⚠  No Local Models",
                border_style="yellow",
            )
        )
        if typer.confirm(
            "Switch to Ollama cloud instead?", default=False
        ):
            _setup_ollama_cloud()
        else:
            console.print(
                "[dim]Skipping LLM setup. "
                "Run `atrophy config` later.[/dim]"
            )
        return

    t = Table(
        title="Local Ollama Models", border_style="yellow"
    )
    t.add_column("#", width=3)
    t.add_column("Model Name", style="yellow")
    t.add_column("Size", justify="right")
    t.add_column("Parameters", justify="right")
    t.add_column("Family")
    for i, m in enumerate(local_models, 1):
        t.add_row(
            str(i),
            m["name"],
            f"{m['size_gb']} GB",
            m["parameter_size"],
            m["family"],
        )
    console.print(t)

    raw = typer.prompt("Model # or name", default="1")
    if raw.isdigit() and 1 <= int(raw) <= len(local_models):
        model_name = local_models[int(raw) - 1]["name"]
    else:
        model_name = raw

    console.print(
        f"[green]✓ Selected local model:[/green] "
        f"{model_name}"
    )
    _save_settings(
        llm_provider="ollama",
        ollama_mode="local",
        ollama_model=model_name,
    )


def _setup_ollama_cloud() -> None:
    """Pick an Ollama cloud model."""
    console.print(
        Panel(
            "Ollama's cloud lets you run large models "
            "without a GPU.\n"
            "Create an API key at: "
            "[link]https://ollama.com/settings/keys[/link]",
            title="🦙 Ollama Cloud",
            border_style="yellow",
        )
    )

    cloud_key = getpass.getpass(
        "Paste Ollama API key (hidden): "
    )
    if not cloud_key.strip():
        console.print(
            "[yellow]No key entered — skipping.[/yellow]"
        )
        return

    cloud_models: list[dict] = []
    with console.status(
        "Fetching available cloud models..."
    ):
        from atrophy.providers.ollama_provider import (
            OllamaProvider,
        )

        try:
            cloud_models = asyncio.run(
                OllamaProvider.list_cloud_models(
                    cloud_key.strip()
                )
            )
        except ProviderError as exc:
            console.print(f"[red]{exc}[/red]")
            console.print(
                "[dim]Skipping setup. Run "
                "`atrophy config` to retry.[/dim]"
            )
            return

    if cloud_models:
        t = Table(
            title="Ollama Cloud Models",
            border_style="yellow",
        )
        t.add_column("#", width=3)
        t.add_column("Model Name", style="yellow")
        for i, m in enumerate(cloud_models, 1):
            t.add_row(str(i), m["name"])
        console.print(t)

        raw = typer.prompt(
            "Model # or name", default="1"
        )
        if raw.isdigit() and 1 <= int(raw) <= len(
            cloud_models
        ):
            model_name = cloud_models[int(raw) - 1]["name"]
        else:
            model_name = raw
    else:
        console.print(
            "[yellow]No cloud models returned — "
            "enter model name manually[/yellow]"
        )
        model_name = typer.prompt(
            "Model name", default="llama3.3:70b"
        )

    console.print(
        f"[green]✓ Selected cloud model:[/green] "
        f"{model_name}"
    )
    _save_settings(
        llm_provider="ollama",
        ollama_mode="cloud",
        ollama_cloud_model=model_name,
    )
    _save_env_key(
        "ATROPHY_OLLAMA_CLOUD_API_KEY", cloud_key.strip()
    )
    _print_key_reminder()


# ── Skip ────────────────────────────────────────────────────────


def _setup_skip() -> None:
    """User chose to skip LLM setup."""
    console.print(
        "[dim]Skipping LLM setup. "
        "Challenges won't be generated.[/dim]"
    )
    console.print(
        "[dim]Run `atrophy config` at any time "
        "to add a provider.[/dim]"
    )
    _save_settings(llm_provider="none")


# ── Persistence helpers ─────────────────────────────────────────


def _save_settings(**kwargs) -> None:
    """Update and persist non-secret settings.

    Args:
        **kwargs: Settings field names and values to update.
    """
    settings = get_settings()
    for k, v in kwargs.items():
        setattr(settings, k, v)
    settings.save()


def _save_env_key(env_var: str, value: str) -> None:
    """Write an API key to ~/.atrophy/.env via python-dotenv.

    SECURITY: Keys are ONLY stored in the .env file, never in
    config.json. The .env file is loaded by pydantic-settings
    on startup.

    Args:
        env_var: The environment variable name (e.g.
            ATROPHY_OPENAI_API_KEY).
        value: The raw API key value.
    """
    import os

    from dotenv import set_key

    settings = get_settings()
    env_path = settings.data_dir / ".env"
    # Ensure the file exists
    env_path.touch(exist_ok=True)
    set_key(str(env_path), env_var, value)

    # Also set in current process so it's immediately usable
    os.environ[env_var] = value


def _print_key_reminder() -> None:
    """Print a reminder about where API keys are stored."""
    settings = get_settings()
    console.print(
        f"[dim]API keys saved to "
        f"{settings.data_dir / '.env'} "
        f"(never committed to git)[/dim]"
    )
