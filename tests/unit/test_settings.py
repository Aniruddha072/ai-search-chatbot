import pytest

from src.config.settings import Settings, get_settings


def test_settings_loads_with_valid_keys(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")

    settings = Settings(_env_file=None)

    assert settings.tavily_api_key == "tavily-test-key"
    assert settings.groq_api_key == "groq-test-key"
    assert settings.log_level == "CRITICAL"
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


def test_settings_loads_context_defaults(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")

    settings = Settings(_env_file=None)

    assert settings.context_token_budget == 2500
    assert settings.max_context_sources == 6
    assert settings.content_fetch_timeout_seconds == 10.0


@pytest.mark.parametrize(
    "field, invalid_value",
    [
        ("CONTEXT_TOKEN_BUDGET", "1000"),  # must be > 1000, not >=
        ("CONTEXT_TOKEN_BUDGET", "500"),
        ("MAX_CONTEXT_SOURCES", "0"),
        ("MAX_CONTEXT_SOURCES", "-1"),
        ("CONTENT_FETCH_TIMEOUT_SECONDS", "0"),
        ("CONTENT_FETCH_TIMEOUT_SECONDS", "-5"),
    ],
)
def test_settings_rejects_out_of_range_context_values(monkeypatch, field, invalid_value):
    monkeypatch.setenv("TAVILY_API_KEY", "tavily-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv(field, invalid_value)

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
