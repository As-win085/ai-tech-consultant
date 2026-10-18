"""Environment-driven configuration for the Knowledge Brain.

Configuration is read from environment variables and an optional local ``.env``
file (which is git-ignored). Secrets are never logged. Validation errors are
raised as actionable messages so misconfiguration fails fast at startup rather
than mid-run.
"""

import os

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = ".env"

DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "openai_compatible": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

DEFAULT_CHAT_BASE_URLS = {
    "anthropic": "https://api.anthropic.com/v1",
    "openai": "https://api.openai.com/v1",
    "openai_compatible": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


class EmbeddingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EMBEDDING_", env_file=ENV_FILE, extra="ignore", populate_by_name=True
    )

    provider: str = "gemini"
    model: str | None = "gemini-embedding-001"
    dimensions: int | None = None
    api_key: str | None = Field(default=None, validation_alias=AliasChoices("EMBEDDING_API_KEY", "LLM_API_KEY", "GEMINI_API_KEY"))
    base_url: str | None = None
    batch_size: int = 64
    timeout: float = 30.0
    max_retries: int = 3

    def effective_base_url(self) -> str | None:
        if self.base_url:
            return self.base_url.rstrip("/")
        return DEFAULT_BASE_URLS.get(self.provider.lower())


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str | None = None


class ChatSettings(BaseSettings):
    """Chat/LLM provider configuration (Milestone 5 answer generation).

    The provider is externalized so no model name is hardcoded. Anthropic is the
    documented default provider for this project; ``ANTHROPIC_API_KEY`` and
    ``ANTHROPIC_MODEL`` are accepted as fallbacks for ``CHAT_API_KEY`` and
    ``CHAT_MODEL`` so existing conventions keep working.
    """

    model_config = SettingsConfigDict(
        env_prefix="CHAT_", env_file=ENV_FILE, extra="ignore", populate_by_name=True
    )

    provider: str = Field(default="gemini", validation_alias=AliasChoices("LLM_PROVIDER", "CHAT_PROVIDER"))
    model: str | None = Field(default=None, validation_alias=AliasChoices("LLM_MODEL", "CHAT_MODEL"))
    api_key: str | None = Field(default=None, validation_alias=AliasChoices("LLM_API_KEY", "CHAT_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"))
    base_url: str | None = Field(default=None, validation_alias=AliasChoices("LLM_BASE_URL", "CHAT_BASE_URL"))
    timeout: float = 60.0
    max_retries: int = 2
    max_tokens: int = 1024
    temperature: float = 0.0

    def resolved_model(self) -> str | None:
        return (os.environ.get("LLM_MODEL") or self.model
                or os.environ.get("ANTHROPIC_MODEL")
                or ("gemini-3.8-flash" if self.provider.lower() in {"gemini", "google"} else None))

    def resolved_api_key(self) -> str | None:
        return (os.environ.get("LLM_API_KEY") or self.api_key
                or os.environ.get("ANTHROPIC_API_KEY"))

    def effective_base_url(self) -> str | None:
        if self.base_url:
            return self.base_url.rstrip("/")
        return (os.environ.get("LLM_BASE_URL") or
                DEFAULT_CHAT_BASE_URLS.get(os.environ.get("LLM_PROVIDER", self.provider).lower()))


class RetrievalSettings(BaseSettings):
    """Retrieval parameters, overridable per request."""

    model_config = SettingsConfigDict(
        env_prefix="RETRIEVAL_", env_file=ENV_FILE, extra="ignore"
    )

    top_k: int = 5
    min_score: float = 0.35
    max_per_article: int = 2
    oversample: int = 4


class AnswerSettings(BaseSettings):
    """Grounded answer generation limits."""

    model_config = SettingsConfigDict(
        env_prefix="ANSWER_", env_file=ENV_FILE, extra="ignore"
    )

    max_context_chars: int = 6000
    max_citations: int = 6
    max_generation_attempts: int = 2


def get_embedding_settings() -> EmbeddingSettings:
    return EmbeddingSettings()


def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()


def get_chat_settings() -> ChatSettings:
    return ChatSettings()


def get_retrieval_settings() -> RetrievalSettings:
    return RetrievalSettings()


def get_answer_settings() -> AnswerSettings:
    return AnswerSettings()


def require_database_url() -> str:
    url = get_database_settings().database_url
    if not url:
        raise ConfigError(
            "DATABASE_URL is not set. Point it at a PostgreSQL database with the "
            "pgvector extension, e.g. "
            "postgresql://postgres:postgres@localhost:55432/knowledge_brain"
        )
    return url
