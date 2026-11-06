from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables and an optional .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "IT Cluster Social Network"
    environment: str = "development"
    debug: bool = False
    # Required on purpose: fail fast at startup instead of guessing a database.
    database_url: str

    # Required, no default: anyone who knows this key can forge a valid token for any
    # user. At least 32 characters, because HS256 uses a 256-bit key and a shorter one
    # is easier to guess.
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    # Short-lived on purpose: a stateless token cannot be revoked before it expires.
    access_token_expire_minutes: int = Field(default=30, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so the environment is parsed only once."""
    return Settings()
