from typing import Annotated

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Redis(BaseModel):
    """Redis configuration model."""

    url: Annotated[
        str | None,
        Field(
            description="Redis connection URL",
        ),
    ] = None
    options: Annotated[
        str | None,
        Field(description="Redis connection options, e.g. 'socket_timeout=5,ssl=True'."),
    ] = None
    sentinels: Annotated[
        str | None,
        Field(
            description="Redis Sentinels",
        ),
    ] = None
    servicename: Annotated[
        str | None,
        Field(
            description="Redis service name for Sentinel",
        ),
    ] = None
    db: Annotated[int, Field(description="Redis database number")] = 0


class Settings(BaseSettings, extra="ignore"):
    """Application settings."""

    redis: Annotated[
        Redis,
        Field(
            description="Redis configuration settings",
        ),
    ] = Redis()

    model_config = SettingsConfigDict(env_prefix="C2C__", env_nested_delimiter="__")


settings = Settings()
