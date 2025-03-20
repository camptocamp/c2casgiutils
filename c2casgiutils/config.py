from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings, extra="ignore"):
    """Application settings."""

    model_config = SettingsConfigDict(env_prefix="C2C_")


settings = Settings()
