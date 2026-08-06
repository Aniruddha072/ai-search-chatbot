from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central, validated configuration for the whole pipeline.

    Every field here is either read from the environment / .env file or
    falls back to the default given. Required fields with no default
    (tavily_api_key, groq_api_key) will raise a single ValidationError
    listing everything missing if the app is started without them,
    instead of failing later inside whichever component first needs
    the key.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    tavily_api_key: str = Field(..., min_length=1)
    groq_api_key: str = Field(..., min_length=1)

    log_level: str = Field(default="INFO")
    environment: str = Field(default="development")

    search_timeout_seconds: float = Field(default=10.0, gt=0)
    max_search_results: int = Field(default=5, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process and reuse the same instance.

    lru_cache with no arguments memoizes on the (empty) argument list,
    so the first call reads and validates the environment, and every
    later call anywhere in the app gets the same cached object back
    instead of re-reading .env each time.
    """
    return Settings()
