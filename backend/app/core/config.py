"""Application settings powered by Pydantic Settings v2."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "SER Inventory Management System API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # PostgreSQL
    DATABASE_URL: str = (
        "postgresql+psycopg://ser_admin:change-me-in-local-dev@localhost:5432/ser_inventory"
    )
    DB_ECHO: bool = False

    # Security / JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Future AI Module (isolated and disabled by default)
    AI_ENABLED: bool = False
    AI_PROVIDER: str = "none"
    AI_API_KEY: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()


settings = get_settings()

