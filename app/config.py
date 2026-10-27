from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables and an optional .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "IT Cluster Social Network"
    environment: str = "development"
    debug: bool = False
    # Required on purpose: fail fast at startup instead of guessing a database.
    database_url: str


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so the environment is parsed only once."""
    return Settings()
