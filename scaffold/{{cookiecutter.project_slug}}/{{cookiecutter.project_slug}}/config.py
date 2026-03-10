from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Variables use the prefix ``{{cookiecutter.project_slug|upper}}__``.
    Nested settings use ``__`` as a delimiter.

    Example: ``{{cookiecutter.project_slug|upper}}__DEBUG=true``
    """

    debug: Annotated[bool, Field(description="Enable debug mode")] = False

    model_config = SettingsConfigDict(
        env_prefix="{{cookiecutter.project_slug|upper}}__",
        env_nested_delimiter="__",
    )


settings = Settings()
