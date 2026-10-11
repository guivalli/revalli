from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://revalli:revalli@localhost:5432/revalli"
    redis_url: str = "redis://localhost:6379/0"

    # Endereço público usado para montar links de convite (ex.: https://revalli.exemplo.org)
    public_url: str = "http://localhost:8080"
    # Marque como true quando o acesso for por HTTPS
    cookie_secure: bool = False
    session_days: int = 14
    invite_days: int = 7

    login_max_attempts: int = 10
    login_window_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
