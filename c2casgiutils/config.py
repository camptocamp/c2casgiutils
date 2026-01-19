import os
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Redis(BaseModel):
    """Redis configuration."""

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


class Prometheus(BaseModel):
    """Prometheus configuration."""

    prefix: Annotated[
        str,
        Field(
            description="Prefix for Prometheus metrics",
        ),
    ] = "c2casgiutils_"
    port: Annotated[int, Field(description="Port for Prometheus metrics")] = 9000


class Sentry(BaseModel):
    """
    Sentry configuration.

    See also: https://docs.sentry.io/platforms/python/configuration/options/#core-options
    """

    dsn: Annotated[str | None, Field(description="Sentry DSN")] = None
    debug: Annotated[bool, Field(description="Enable Sentry debug mode")] = False
    release: Annotated[str | None, Field(description="Sentry release version")] = None
    environment: Annotated[str, Field(description="Sentry environment")] = "production"
    dist: Annotated[str | None, Field(description="Sentry distribution")] = None
    sample_rate: Annotated[float, Field(description="Sample rate for error events")] = 1.0
    ignore_errors: Annotated[list[str], Field(description="List of exception class names to ignore")] = []
    max_breadcrumbs: Annotated[int, Field(description="Maximum number of breadcrumbs to capture")] = 100
    attach_stacktrace: Annotated[bool, Field(description="Attach stack trace to all messages")] = False
    send_default_pii: Annotated[bool | None, Field(description="Send default PII")] = None
    event_scrubber: Annotated[str | None, Field(description="Event scrubber for sensitive information")] = (
        None
    )
    include_source_context: Annotated[bool, Field(description="Include source context in events")] = True
    include_local_variables: Annotated[bool, Field(description="Include local variables in events")] = True
    add_full_stack: Annotated[bool, Field(description="Add full stack trace to events")] = False
    max_stack_frames: Annotated[int, Field(description="Maximum number of stack frames to capture")] = 100
    server_name: Annotated[str | None, Field(description="Server name for Sentry events")] = None
    project_root: Annotated[str, Field(description="Root directory of the project")] = str(Path.cwd())
    in_app_include: Annotated[
        list[str],
        Field(description="List of module prefixes that are in the app"),
    ] = []
    in_app_exclude: Annotated[
        list[str],
        Field(description="List of module prefixes that are not in the app"),
    ] = []
    max_request_body_size: Annotated[str, Field(description="Maximum request body size to capture")] = (
        "medium"
    )
    max_value_length: Annotated[int, Field(description="Maximum length of values in event payloads")] = 1024
    ca_certs: Annotated[str | None, Field(description="Path to alternative CA bundle file in PEM format")] = (
        None
    )
    send_client_reports: Annotated[bool, Field(description="Send client reports to Sentry")] = True
    tags: Annotated[
        dict[str, str],
        Field(
            description="Default tags for Sentry events, loaded from environment variables with prefix `C2C__SENTRY__TAG_`",
        ),
    ] = {}

    @field_validator("tags", mode="before")
    @classmethod
    def build_config_dict(cls, value: dict[str, str] | None) -> dict[str, str]:
        """Build the tags dictionary from environment variables."""
        del value

        # Get all environment variables that start with "C2C__SENTRY__TAG__"
        prefix = "C2C__SENTRY__TAG_"
        return {
            key[len(prefix) :].lower(): value for key, value in os.environ.items() if key.startswith(prefix)
        }


class AuthGitHub(BaseModel):
    """GitHub Authentication settings."""

    repository: Annotated[
        str | None,
        Field(description="GitHub repository for authentication"),
    ] = None
    access_type: Annotated[str, Field(description="GitHub access type")] = "pull"
    authorize_url: Annotated[
        str,
        Field(description="GitHub OAuth authorization URL"),
    ] = "https://github.com/login/oauth/authorize"
    token_url: Annotated[
        str,
        Field(description="GitHub OAuth token URL"),
    ] = "https://github.com/login/oauth/access_token"  # noqa: S105
    user_url: Annotated[str, Field(description="GitHub user API URL")] = "https://api.github.com/user"
    repo_url: Annotated[
        str,
        Field(description="GitHub repository API URL"),
    ] = "https://api.github.com/repos"
    client_id: Annotated[str | None, Field(description="GitHub OAuth client ID")] = None
    client_secret: Annotated[str | None, Field(description="GitHub OAuth client secret")] = None
    scope: Annotated[str, Field(description="GitHub OAuth scope")] = "repo"
    proxy_url: Annotated[str | None, Field(description="GitHub proxy URL")] = None
    state_cookie: Annotated[str, Field(description="GitHub state cookie name")] = "c2c-state"
    state_cookie_age: Annotated[
        int,
        Field(description="GitHub state cookie age in seconds (default: 10 minutes)"),
    ] = 10 * 60  # 10 minutes


class AuthJWTCookie(BaseModel):
    """JWT cookie settings."""

    same_site: Annotated[
        Literal["lax", "strict", "none"],
        Field(
            description="SameSite attribute for JWT cookie (default: strict)",
        ),
    ] = "strict"
    secure: Annotated[
        bool,
        Field(
            description="Whether the JWT cookie should be secure (default: True)",
        ),
    ] = True
    path: Annotated[
        str | None,
        Field(
            description="Path for the JWT cookie (default: the path to the index page)",
        ),
    ] = None


class AuthJWT(BaseModel):
    """JWT Authentication settings used to store the cookies."""

    secret: Annotated[str | None, Field(description="JWT secret key")] = None
    algorithm: Annotated[str, Field(description="JWT algorithm (default: HS256)")] = "HS256"
    cookie: Annotated[AuthJWTCookie, Field(description="JWT cookie settings")] = AuthJWTCookie()


class AuthTest(BaseModel):
    """Test Authentication settings."""

    username: Annotated[str | None, Field(description="Test username")] = None


class Auth(BaseModel):
    """C2C Authentication settings."""

    # GitHub authentication settings
    cookie_age: Annotated[
        int,
        Field(description="Authentication cookie age in seconds (default: 7 days)"),
    ] = 7 * 24 * 3600  # 7 days
    cookie: Annotated[str, Field(description="Authentication cookie name")] = "c2c-auth"
    jwt: Annotated[AuthJWT, Field(description="JWT authentication settings")] = AuthJWT()

    # Trivial auth (not secure)
    secret: Annotated[
        str | None,
        Field(description="Secret key for trivial authentication (not secure)"),
    ] = None

    # GitHub Authentication settings
    github: Annotated[
        AuthGitHub,
        Field(description="GitHub authentication settings"),
    ] = AuthGitHub()

    test: Annotated[
        AuthTest,
        Field(description="Test authentication settings"),
    ] = AuthTest()


class SettingsToolsLogging(BaseModel):
    """C2C Tools logging settings."""

    redis_prefix: Annotated[
        str,
        Field(
            description="Redis prefix for logging settings",
        ),
    ] = "c2c_logging_level_"
    application_module: Annotated[
        str,
        Field(
            description="Application module name for logging",
        ),
    ] = "c2casgiutils"


class SettingsTools(BaseModel):
    """C2C Tools settings."""

    logging: Annotated[
        SettingsToolsLogging,
        Field(
            description="Settings for logging tools",
        ),
    ] = SettingsToolsLogging()


class Settings(BaseSettings, extra="ignore"):
    """Application settings."""

    redis: Annotated[
        Redis,
        Field(
            description="Redis configuration settings",
        ),
    ] = Redis()
    prometheus: Annotated[
        Prometheus,
        Field(
            description="Prometheus configuration settings",
        ),
    ] = Prometheus()
    sentry: Annotated[
        Sentry,
        Field(
            description="Sentry configuration settings",
        ),
    ] = Sentry()
    auth: Annotated[
        Auth,
        Field(description="Authentication settings"),
    ] = Auth()
    tools: Annotated[
        SettingsTools,
        Field(description="Tools settings"),
    ] = SettingsTools()

    model_config = SettingsConfigDict(env_prefix="C2C__", env_nested_delimiter="__")


settings = Settings()
