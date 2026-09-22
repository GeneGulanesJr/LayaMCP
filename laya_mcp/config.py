"""Settings for LayaMCP, env-overridable via LAYAMCP_* prefix."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Override via env or .env file.

    Examples:
        LAYAMCP_PORT=9000 layamcp
        LAYAMCP_PRELOAD_MODELS=false layamcp
    """

    model_config = SettingsConfigDict(
        env_prefix="LAYAMCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8765
    preload_models: bool = True
    log_level: str = "INFO"


settings = Settings()