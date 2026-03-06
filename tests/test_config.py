"""Tests for atrophy.config — Settings, secrets, and persistence."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from atrophy.config import Settings
from atrophy.exceptions import ProviderError


class TestSettingsFromEnv:
    """Verify Settings reads from ATROPHY_ environment variables."""

    def test_env_vars_override_defaults(self, tmp_path: Path) -> None:
        """ATROPHY_ env vars should take precedence over defaults."""
        env = {
            "ATROPHY_LLM_PROVIDER": "openai",
            "ATROPHY_OPENAI_API_KEY": "sk-test-key-12345",
            "ATROPHY_DATA_DIR": str(tmp_path / ".atrophy"),
        }
        with patch.dict(os.environ, env, clear=False):
            settings = Settings(data_dir=tmp_path / ".atrophy")

        assert settings.llm_provider == "openai"
        assert settings.openai_api_key is not None
        assert isinstance(settings.openai_api_key, SecretStr)

    def test_default_provider_is_none(self, tmp_path: Path) -> None:
        """Without env vars, provider should default to 'none'."""
        settings = Settings(data_dir=tmp_path / ".atrophy")
        assert settings.llm_provider == "none"


class TestSecretStrBehavior:
    """Verify API keys are SecretStr and never leak."""

    def test_openai_key_accessible_via_getter(self, tmp_path: Path) -> None:
        """get_openai_key() should return the raw key string."""
        env = {
            "ATROPHY_LLM_PROVIDER": "openai",
            "ATROPHY_OPENAI_API_KEY": "sk-test-key-12345",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = Settings(data_dir=tmp_path / ".atrophy")

        assert settings.get_openai_key() == "sk-test-key-12345"

    def test_openai_key_hidden_in_repr(self, tmp_path: Path) -> None:
        """SecretStr must show '**********' when printed, not the raw key."""
        env = {
            "ATROPHY_LLM_PROVIDER": "openai",
            "ATROPHY_OPENAI_API_KEY": "sk-test-key-12345",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = Settings(data_dir=tmp_path / ".atrophy")

        # str() and repr() of SecretStr must hide the value
        key_str = str(settings.openai_api_key)
        assert "sk-test" not in key_str
        assert "**" in key_str

    def test_anthropic_key_accessible_via_getter(self, tmp_path: Path) -> None:
        """get_anthropic_key() should return the raw key string."""
        env = {
            "ATROPHY_LLM_PROVIDER": "anthropic",
            "ATROPHY_ANTHROPIC_API_KEY": "sk-ant-test-key",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = Settings(data_dir=tmp_path / ".atrophy")

        assert settings.get_anthropic_key() == "sk-ant-test-key"

    def test_get_openai_key_raises_when_missing(self, tmp_path: Path) -> None:
        """get_openai_key() must raise ProviderError if key is None."""
        settings = Settings(data_dir=tmp_path / ".atrophy")
        with pytest.raises(ProviderError, match="OpenAI API key not configured"):
            settings.get_openai_key()

    def test_get_anthropic_key_raises_when_missing(
        self, tmp_path: Path
    ) -> None:
        """get_anthropic_key() must raise ProviderError if key is None."""
        settings = Settings(data_dir=tmp_path / ".atrophy")
        with pytest.raises(
            ProviderError, match="Anthropic API key not configured"
        ):
            settings.get_anthropic_key()


class TestSaveExcludesSecrets:
    """Verify save() NEVER writes API keys to disk."""

    def test_save_excludes_api_keys(self, tmp_path: Path) -> None:
        """The saved JSON must not contain openai_api_key or anthropic_api_key."""
        env = {
            "ATROPHY_LLM_PROVIDER": "openai",
            "ATROPHY_OPENAI_API_KEY": "sk-test-key-12345",
            "ATROPHY_ANTHROPIC_API_KEY": "sk-ant-secret",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = Settings(data_dir=tmp_path / ".atrophy")

        config_path = settings.save()
        saved = json.loads(config_path.read_text(encoding="utf-8"))

        # Keys must be absent from the JSON
        assert "openai_api_key" not in saved
        assert "anthropic_api_key" not in saved
        # The raw key value must not appear anywhere in the file
        raw_content = config_path.read_text(encoding="utf-8")
        assert "sk-test-key-12345" not in raw_content
        assert "sk-ant-secret" not in raw_content

    def test_save_includes_non_secret_fields(self, tmp_path: Path) -> None:
        """Non-secret settings should be present in the saved JSON."""
        settings = Settings(
            data_dir=tmp_path / ".atrophy",
            llm_provider="ollama",
            default_days_back=30,
        )
        config_path = settings.save()
        saved = json.loads(config_path.read_text(encoding="utf-8"))

        assert saved["llm_provider"] == "ollama"
        assert saved["default_days_back"] == 30

    def test_save_excludes_db_path(self, tmp_path: Path) -> None:
        """db_path is computed, should not be in the saved config."""
        settings = Settings(data_dir=tmp_path / ".atrophy")
        config_path = settings.save()
        saved = json.loads(config_path.read_text(encoding="utf-8"))

        assert "db_path" not in saved


class TestModelValidator:
    """Verify model validators run correctly."""

    def test_db_path_computed_from_data_dir(self, tmp_path: Path) -> None:
        """db_path should be data_dir / 'atrophy.db'."""
        data_dir = tmp_path / ".atrophy"
        settings = Settings(data_dir=data_dir)
        assert settings.db_path == data_dir / "atrophy.db"

    def test_data_dir_created_on_init(self, tmp_path: Path) -> None:
        """data_dir should be created automatically."""
        data_dir = tmp_path / "nested" / "deep" / ".atrophy"
        settings = Settings(data_dir=data_dir)
        assert settings.data_dir.exists()
        assert settings.data_dir.is_dir()


class TestValidateProvider:
    """Verify validate_provider() returns correct status."""

    def test_none_provider_is_always_valid(self, tmp_path: Path) -> None:
        """Provider 'none' should always pass validation."""
        settings = Settings(data_dir=tmp_path / ".atrophy")
        valid, msg = settings.validate_provider()
        assert valid is True
        assert msg == ""

    def test_openai_without_key_is_invalid(self, tmp_path: Path) -> None:
        """Provider 'openai' without a key should fail validation."""
        env = {"ATROPHY_LLM_PROVIDER": "openai"}
        with patch.dict(os.environ, env, clear=False):
            settings = Settings(data_dir=tmp_path / ".atrophy")

        valid, msg = settings.validate_provider()
        assert valid is False
        assert "ATROPHY_OPENAI_API_KEY" in msg

    def test_openai_with_key_is_valid(self, tmp_path: Path) -> None:
        """Provider 'openai' with a key should pass validation."""
        env = {
            "ATROPHY_LLM_PROVIDER": "openai",
            "ATROPHY_OPENAI_API_KEY": "sk-test",
        }
        with patch.dict(os.environ, env, clear=False):
            settings = Settings(data_dir=tmp_path / ".atrophy")

        valid, msg = settings.validate_provider()
        assert valid is True
        assert msg == ""

    def test_anthropic_without_key_is_invalid(self, tmp_path: Path) -> None:
        """Provider 'anthropic' without a key should fail validation."""
        env = {"ATROPHY_LLM_PROVIDER": "anthropic"}
        with patch.dict(os.environ, env, clear=False):
            settings = Settings(data_dir=tmp_path / ".atrophy")

        valid, msg = settings.validate_provider()
        assert valid is False
        assert "ATROPHY_ANTHROPIC_API_KEY" in msg

    def test_ollama_is_valid_by_default(self, tmp_path: Path) -> None:
        """Provider 'ollama' should pass with default localhost URL."""
        settings = Settings(
            data_dir=tmp_path / ".atrophy",
            llm_provider="ollama",
        )
        valid, msg = settings.validate_provider()
        assert valid is True


class TestOllamaSSRFGuard:
    """Verify Ollama URL is restricted to localhost."""

    def test_ollama_rejects_external_url(self, tmp_path: Path) -> None:
        """Non-localhost Ollama URL must raise ValueError."""
        with pytest.raises(ValueError, match="SSRF prevention"):
            Settings(
                data_dir=tmp_path / ".atrophy",
                llm_provider="ollama",
                ollama_base_url="http://evil.com:11434",
            )

    def test_ollama_accepts_localhost(self, tmp_path: Path) -> None:
        """http://localhost URL should be accepted."""
        settings = Settings(
            data_dir=tmp_path / ".atrophy",
            llm_provider="ollama",
            ollama_base_url="http://localhost:11434",
        )
        assert settings.ollama_base_url == "http://localhost:11434"

    def test_ollama_accepts_127_0_0_1(self, tmp_path: Path) -> None:
        """http://127.0.0.1 URL should be accepted."""
        settings = Settings(
            data_dir=tmp_path / ".atrophy",
            llm_provider="ollama",
            ollama_base_url="http://127.0.0.1:11434",
        )
        assert settings.ollama_base_url == "http://127.0.0.1:11434"


class TestEmailValidation:
    """Verify author_email format validation."""

    def test_valid_email_accepted(self, tmp_path: Path) -> None:
        """A properly formatted email should be accepted."""
        settings = Settings(
            data_dir=tmp_path / ".atrophy",
            author_email="dev@example.com",
        )
        assert settings.author_email == "dev@example.com"

    def test_invalid_email_rejected(self, tmp_path: Path) -> None:
        """An improperly formatted email should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid email format"):
            Settings(
                data_dir=tmp_path / ".atrophy",
                author_email="not-an-email",
            )

    def test_none_email_accepted(self, tmp_path: Path) -> None:
        """None email (the default) should be valid."""
        settings = Settings(data_dir=tmp_path / ".atrophy")
        assert settings.author_email is None


class TestConfigFilePersistence:
    """Verify round-trip save → load."""

    def test_save_and_reload(self, tmp_path: Path) -> None:
        """Settings saved to JSON should reload correctly."""
        original = Settings(
            data_dir=tmp_path / ".atrophy",
            llm_provider="ollama",
            default_days_back=30,
            ollama_model="codellama",
        )
        config_path = original.save()

        reloaded = Settings.from_config_file(config_path)
        assert reloaded.llm_provider == "ollama"
        assert reloaded.default_days_back == 30
        assert reloaded.ollama_model == "codellama"


class TestConfigRules:
    """Explicit tests for config security rules."""

    def test_secretstr_never_leaks_in_str(self) -> None:
        """SecretStr must not leak its value in str()."""
        settings = Settings(
            openai_api_key=SecretStr("super-secret-key-123"),
            data_dir=Path("/tmp/.atrophy"),
        )
        output = str(settings)
        assert "super-secret-key-123" not in output
        assert "**********" in output or "SecretStr" in output

    def test_save_excludes_api_keys(self, tmp_path: Path) -> None:
        """save() must never write API keys to disk."""
        data_dir = tmp_path / ".atrophy"
        settings = Settings(
            data_dir=data_dir,
            openai_api_key=SecretStr("will-not-save"),
            anthropic_api_key=SecretStr("also-will-not-save"),
        )
        config_file = settings.save()

        with open(config_file) as f:
            data = json.load(f)

        assert "openai_api_key" not in data
        assert "anthropic_api_key" not in data
        assert "data_dir" in data
