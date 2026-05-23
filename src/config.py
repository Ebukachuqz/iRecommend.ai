from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.constants import (
    DEFAULT_CATEGORY,
    DEFAULT_GROQ_MODEL,
    DEFAULT_PERSONA_PROMPT_VERSION,
    DEFAULT_PERSONA_VERSION,
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_public_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_PUBLIC_KEY", "SUPABASE_ANON_KEY"),
    )
    supabase_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY"),
    )
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    hf_token: str | None = Field(default=None, alias="HF_TOKEN")

    default_category: str = Field(default=DEFAULT_CATEGORY, alias="DEFAULT_CATEGORY")
    groq_model: str = Field(default=DEFAULT_GROQ_MODEL, alias="GROQ_MODEL")
    persona_version: str = Field(default=DEFAULT_PERSONA_VERSION, alias="PERSONA_VERSION")
    persona_prompt_version: str = Field(
        default=DEFAULT_PERSONA_PROMPT_VERSION,
        alias="PERSONA_PROMPT_VERSION",
    )
    log_dir: Path = Field(default=Path("logs"), alias="LOG_DIR")

    def require_supabase(self) -> tuple[str, str]:
        """Return URL and backend key, preferring the service role key."""

        key = self.supabase_secret_key or self.supabase_public_key
        if not self.supabase_url or not key:
            raise RuntimeError("SUPABASE_URL and a Supabase key must be configured.")
        return self.supabase_url, key

    def require_groq_api_key(self) -> str:
        if not self.groq_api_key:
            raise RuntimeError("GROQ_API_KEY must be configured for LLM calls.")
        return self.groq_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
