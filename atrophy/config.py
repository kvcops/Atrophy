"""Configuration management for atrophy.

Uses pydantic-settings v2 to load settings from environment variables
(prefix ATROPHY_), an optional JSON config file at ~/.atrophy/config.json,
and sensible defaults. API keys are stored as SecretStr and are NEVER
written to disk or logged.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for atrophy.

    Reads from (in order of priority):
    1. Environment variables with ATROPHY_ prefix
    2. ~/.atrophy/config.json (if it exists)
    3. Field defaults below
    """

    model_config = SettingsConfigDict(
        env_prefix="ATROPHY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM Provider ────────────────────────────────────────────────
    llm_provider: Literal["openai", "anthropic", "ollama", "none"] = "none"
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # ── Scan settings ───────────────────────────────────────────────
    default_days_back: int = Field(default=180, ge=7, le=3650)
    author_email: str | None = None
    exclude_patterns: list[str] = [
        "package-lock.json",
        "yarn.lock",
        "*.lock",
        "*.min.js",
        "*.min.css",
        "__pycache__/*",
        "dist/*",
        "build/*",
        "*.pyc",
        ".env*",
    ]

    # ── Storage ─────────────────────────────────────────────────────
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".atrophy")
    db_path: Path | None = Field(default=None)

    # ── Validators ──────────────────────────────────────────────────

    @model_validator(mode="after")
    def _set_db_path_and_ensure_data_dir(self) -> "Settings":
        """Compute db_path from data_dir and create the data directory."""
        self.db_path = self.data_dir / "atrophy.db"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self

    @model_validator(mode="after")
    def _validate_ollama_url(self) -> "Settings":
        """SSRF guard — Ollama URL must point to localhost."""
        if self.llm_provider == "ollama":
            allowed = (
                self.ollama_base_url.startswith("http://localhost")
                or self.ollama_base_url.startswith("http://127.0.0.1")
            )
            if not allowed:
                msg = (
                    "Ollama base URL must start with http://localhost or "
                    "http://127.0.0.1 (SSRF prevention). "
                    f"Got: {self.ollama_base_url}"
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_author_email_format(self) -> "Settings":
        """Validate author_email if provided."""
        if self.author_email is not None:
            pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
            if not re.match(pattern, self.author_email):
                msg = f"Invalid email format: {self.author_email}"
                raise ValueError(msg)
        return self

    # ── Secret accessors ────────────────────────────────────────────

    def get_openai_key(self) -> str:
        """Return the raw OpenAI API key string.

        Only call this at the exact moment the key is needed (e.g. when
        constructing the OpenAI client). Never store the return value.

        Raises:
            ValueError: If no OpenAI API key is configured.
        """
        if self.openai_api_key is None:
            msg = (
                "OpenAI API key not configured. "
                "Set ATROPHY_OPENAI_API_KEY or run `atrophy init`."
            )
            raise ValueError(msg)
        return self.openai_api_key.get_secret_value()

    def get_anthropic_key(self) -> str:
        """Return the raw Anthropic API key string.

        Only call this at the exact moment the key is needed (e.g. when
        constructing the Anthropic client). Never store the return value.

        Raises:
            ValueError: If no Anthropic API key is configured.
        """
        if self.anthropic_api_key is None:
            msg = (
                "Anthropic API key not configured. "
                "Set ATROPHY_ANTHROPIC_API_KEY or run `atrophy init`."
            )
            raise ValueError(msg)
        return self.anthropic_api_key.get_secret_value()

    # ── Provider validation ─────────────────────────────────────────

    def validate_provider(self) -> tuple[bool, str]:
        """Check whether the currently configured provider is usable.

        Returns:
            A tuple of (is_valid, error_message). If valid, error_message
            is an empty string.
        """
        match self.llm_provider:
            case "none":
                return (True, "")
            case "openai":
                if self.openai_api_key is None:
                    return (
                        False,
                        "LLM provider is set to 'openai' but "
                        "ATROPHY_OPENAI_API_KEY is not set. "
                        "Export it or run `atrophy init`.",
                    )
                return (True, "")
            case "anthropic":
                if self.anthropic_api_key is None:
                    return (
                        False,
                        "LLM provider is set to 'anthropic' but "
                        "ATROPHY_ANTHROPIC_API_KEY is not set. "
                        "Export it or run `atrophy init`.",
                    )
                return (True, "")
            case "ollama":
                # URL is already validated by _validate_ollama_url
                return (True, "")
            case _:
                return (False, f"Unknown LLM provider: {self.llm_provider}")

    # ── Persistence ─────────────────────────────────────────────────

    def save(self) -> Path:
        """Save non-secret settings to ~/.atrophy/config.json.

        API keys are NEVER written to disk — they must live in
        environment variables only.

        Returns:
            Path to the saved config file.
        """
        config_path = self.data_dir / "config.json"
        # Exclude secrets and compute-only fields from serialization
        data = self.model_dump(
            mode="json",
            exclude={"openai_api_key", "anthropic_api_key", "db_path"},
        )
        # Convert Path objects to strings for JSON serialization
        if "data_dir" in data and data["data_dir"] is not None:
            data["data_dir"] = str(data["data_dir"])

        config_path.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return config_path

    # ── Config file loading ─────────────────────────────────────────

    @classmethod
    def from_config_file(cls, config_path: Path | None = None) -> "Settings":
        """Load settings from config file, overlaid with env vars.

        Args:
            config_path: Explicit path to config.json. If None, uses
                the default ~/.atrophy/config.json.

        Returns:
            A Settings instance with config file values as defaults,
            overridden by any environment variables.
        """
        if config_path is None:
            config_path = Path.home() / ".atrophy" / "config.json"

        file_values: dict = {}
        if config_path.exists():
            raw = config_path.read_text(encoding="utf-8")
            file_values = json.loads(raw)

        return cls(**file_values)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance.

    Uses lru_cache so Settings is only constructed once per process.
    Reads from environment variables and ~/.atrophy/config.json.
    """
    return Settings.from_config_file()
