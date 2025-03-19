from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings, extra="ignore"):
    """Application settings."""

    BACKEND_CORS_ORIGINS: list[str] | list[AnyHttpUrl]
    API_VERSION: str = "v1"
    API_V1_STR: str = f"/api/{API_VERSION}"


settings = Settings()
