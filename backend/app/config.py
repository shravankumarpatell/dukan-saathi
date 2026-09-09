from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), extra="ignore")

    app_name: str = "TileOS"
    env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(default="postgresql+asyncpg://tileos:tileos@127.0.0.1:5432/tileos", alias="DATABASE_URL")
    jwt_secret: str = Field(default="change-me-in-production-please", alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = Field(default=60, alias="ACCESS_TOKEN_MINUTES")
    refresh_token_days: int = Field(default=14, alias="REFRESH_TOKEN_DAYS")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    auto_bootstrap_pg: bool = Field(default=True, alias="AUTO_BOOTSTRAP_PG")
    seed_on_start: bool = Field(default=True, alias="SEED_ON_START")
    emergent_llm_key: str | None = Field(default=None, alias="EMERGENT_LLM_KEY")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
