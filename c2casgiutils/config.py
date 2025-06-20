from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings, extra="ignore"):
    """Application settings."""

    model_config = SettingsConfigDict(env_prefix="C2C_")

    # Redis settings
    REDIS_URL: str | None = None
    REDIS_OPTIONS: str | None = None
    REDIS_SENTINELS: str | None = None
    REDIS_SERVICENAME: str | None = None
    REDIS_DB: str = "0"


settings = Settings()
