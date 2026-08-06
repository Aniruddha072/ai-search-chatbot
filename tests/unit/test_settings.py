import pytest

from src.config.settings import Settings, get_settings


def test_settings_loads_with_valid_keys(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")

    settings = Settings(_env_file=None)

    assert settings.tavily_api_key == "tavily-test-key"
    assert settings.groq_api_key == "groq-test-key"
    assert settings.log_level == "INFO"
    assert settings.environment == "development"


def test_settings_rejects_missing_keys(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(Exception):
        Settings(_env_file=None)


def test_settings_rejects_empty_key(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "")

    with pytest.raises(Exception):
        Settings(_env_file=None)


def test_get_settings_is_cached(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second
    get_settings.cache_clear()
