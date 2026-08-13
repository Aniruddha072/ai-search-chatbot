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

    # CRITICAL, not INFO: the CLI is a chatbot, not a dev console - nothing
    # in this codebase or its dependencies logs at CRITICAL under any
    # condition seen so far, so the terminal stays silent by default (see
    # Decision 13.3). Set LOG_LEVEL=INFO in .env to see per-stage turn
    # timings and HTTP request logs on stderr for debugging.
    log_level: str = Field(default="CRITICAL")
    environment: str = Field(default="development")

    search_timeout_seconds: float = Field(default=10.0, gt=0)
    max_search_results: int = Field(default=5, gt=0)

    context_token_budget: int = Field(default=2500, gt=1000)
    max_context_sources: int = Field(default=6, gt=0)
    content_fetch_timeout_seconds: float = Field(default=10.0, gt=0)

    groq_fast_model: str = Field(default="llama-3.1-8b-instant", min_length=1)
    groq_capable_model: str = Field(default="llama-3.3-70b-versatile", min_length=1)
    llm_timeout_seconds: float = Field(default=10.0, gt=0)

    evaluation_timeout_seconds: float = Field(default=30.0, gt=0)

    query_plan_cache_ttl_seconds: float = Field(default=600.0, gt=0)
    search_result_cache_ttl_seconds: float = Field(default=3600.0, gt=0)

    # How many recent (question, answer) turns QueryPlanner.plan() gets
    # shown to resolve a follow-up's pronouns/references - a bounded
    # window, not full history, to keep planning-prompt size roughly
    # constant regardless of how long a conversation runs. 0 disables the
    # feature entirely (presentation layers just never build a non-empty
    # ConversationContext to pass in).
    conversation_history_turns: int = Field(default=2, ge=0)

    max_query_length: int = Field(default=500, gt=0)
    max_retry_attempts: int = Field(default=3, gt=0)
    retry_backoff_seconds: float = Field(default=0.5, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process and reuse the same instance.

    lru_cache with no arguments memoizes on the (empty) argument list,
    so the first call reads and validates the environment, and every
    later call anywhere in the app gets the same cached object back
    instead of re-reading .env each time.
    """
    return Settings()
