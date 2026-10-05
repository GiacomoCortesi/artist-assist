"""Application settings loaded from environment."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LlmProvider = Literal["openai", "anthropic"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ArtistAssist"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    database_url: str = "sqlite:///./data/artistassist.db"
    media_root: str = "./storage"
    token_encryption_key: str = "change-me-to-a-32-byte-url-safe-base64-key"

    # Chat: openai | anthropic (Claude). Image generate/edit stays OpenAI-only.
    llm_provider: LlmProvider = "openai"
    llm_live: int = Field(
        default=0,
        validation_alias=AliasChoices("LLM_LIVE", "OPENAI_LIVE"),
    )

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_image_model: str = "gpt-image-1"

    anthropic_api_key: str = ""
    anthropic_chat_model: str = "claude-sonnet-4-6"

    fixture_mode: int | None = Field(
        default=None,
        validation_alias=AliasChoices("FIXTURE_MODE"),
    )
    platform_live: int = Field(
        default=0,
        validation_alias=AliasChoices("PLATFORM_LIVE"),
    )

    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://localhost:8080/api/oauth/spotify/callback"

    soundcloud_client_id: str = ""
    soundcloud_client_secret: str = ""
    soundcloud_redirect_uri: str = "http://localhost:8080/api/oauth/soundcloud/callback"

    deezer_app_id: str = ""
    deezer_app_secret: str = ""
    deezer_redirect_uri: str = "http://localhost:8080/api/oauth/deezer/callback"

    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_redirect_uri: str = "http://localhost:8080/api/oauth/meta/callback"
    meta_page_access_token: str = ""
    meta_page_id: str = ""
    meta_ig_user_id: str = ""
    threads_access_token: str = ""
    threads_user_id: str = ""

    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_redirect_uri: str = "http://localhost:8080/api/oauth/tiktok/callback"

    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_redirect_uri: str = "http://localhost:8080/api/oauth/youtube/callback"

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_public_base_url: str = ""

    sync_cron_hour: int = 3
    sync_cron_minute: int = 0

    @property
    def user_agent(self) -> str:
        return f"ArtistAssist/{self.app_version}"

    @property
    def use_fixtures(self) -> bool:
        if self.fixture_mode is not None:
            return bool(self.fixture_mode)
        return not bool(self.platform_live)


@lru_cache
def get_settings() -> Settings:
    return Settings()
