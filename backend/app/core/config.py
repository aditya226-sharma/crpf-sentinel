"""Application configuration loaded from environment variables."""

import secrets
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Known placeholder values that must never be used as the real JWT secret.
PLACEHOLDER_JWT_SECRETS = {
    "",
    "dev-insecure-secret-change-me-0123456789abcdef",
    "change-me-to-a-long-random-secret-at-least-32-chars",
}


class Settings(BaseSettings):
    """Centralized configuration. All secrets come from the environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    APP_NAME: str = "CyberRakshak"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    API_PREFIX: str = "/api"
    DEBUG: bool = False

    # Security
    JWT_SECRET: str = "dev-insecure-secret-change-me-0123456789abcdef"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    PASSWORD_MIN_LENGTH: int = 12
    AGENT_TOKEN_BYTES: int = 32

    # Database
    DATABASE_URL: str = "sqlite:///./sentinel.db"

    # Criminal Intelligence graph backing store. "relational" is the default
    # (zero-dependency, SQLAlchemy tables). "neo4j" uses the optional driver.
    GRAPH_BACKEND: str = "relational"
    NEO4J_URI: str = ""
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""

    # CORS
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Only trust X-Forwarded-For when the app is behind a trusted reverse proxy.
    TRUST_PROXY: bool = False

    # Rate limiting
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 10
    RATE_LIMIT_INGEST_PER_MINUTE: int = 6000
    RATE_LIMIT_GENERAL_PER_MINUTE: int = 120

    # Seeding
    SEED_DEMO_DATA: bool = False
    SEED_ADMIN_USERNAME: str = "admin"
    SEED_ADMIN_EMAIL: str = "admin@cyberrakshak.demo"
    SEED_ADMIN_PASSWORD: str = "Sentinel@123"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _enforce_secret_strength(self) -> "Settings":
        if self.JWT_SECRET in PLACEHOLDER_JWT_SECRETS:
            if self.APP_ENV == "production":
                raise RuntimeError(
                    "JWT_SECRET must be set to a strong random value in production"
                )
            self.JWT_SECRET = secrets.token_urlsafe(48)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
