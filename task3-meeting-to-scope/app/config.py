"""Environment-driven configuration for the Meeting-to-Scope Agent.

Configuration is read from environment variables and an optional local ``.env``
file (git-ignored). Secrets are never logged. Missing required configuration
fails with an actionable error. The service is designed to run with the
deterministic offline extractor and no database (in-memory store) for tests.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = ".env"


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    # HTTP server
    port: int = 8090
    log_level: str = "info"

    # Task 1 Knowledge Brain
    knowledge_brain_url: str = "http://localhost:8000"
    knowledge_brain_timeout_ms: int = 60000
    knowledge_brain_retries: int = 1

    # Extraction engine
    extractor: str = "rules"  # rules | llm

    # LLM provider (used only when extractor=llm)
    llm_provider: str = "gemini"  # anthropic | openai_compatible | gemini | groq | openrouter | ollama
    llm_model: str | None = "gemini-3.8-flash"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    openrouter_api_key: str | None = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    groq_api_key: str | None = Field(default=None, validation_alias="GROQ_API_KEY")
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    embedding_provider: str = "gemini"
    embedding_model: str = "gemini-embedding-001"
    llm_timeout_ms: int = 60000
    llm_max_retries: int = 1
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.0

    # Transcript ingestion
    transcript_dir: str = "data/transcripts"
    max_transcript_chars: int = 200000

    # Persistence
    database_url: str | None = None
    database_schema: str = "meeting_to_scope"

    @property
    def knowledge_brain_timeout_seconds(self) -> float:
        return self.knowledge_brain_timeout_ms / 1000.0

    @property
    def llm_timeout_seconds(self) -> float:
        return self.llm_timeout_ms / 1000.0


def load_settings(**overrides) -> Settings:
    """Load settings, applying optional explicit overrides (used by tests)."""
    if overrides:
        return Settings(**overrides)
    return Settings()


def require_database_url(settings: Settings) -> str:
    if not settings.database_url:
        raise ConfigError(
            "DATABASE_URL is not set. Point it at a PostgreSQL database, e.g. "
            "postgresql://postgres:postgres@localhost:55432/knowledge_brain"
        )
    return settings.database_url
