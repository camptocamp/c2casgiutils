from typing import Annotated, Literal

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
    ] = "lax"
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


class Settings(BaseSettings, extra="ignore"):
    """Application settings."""

    redis: Annotated[
        Redis,
        Field(
            description="Redis configuration settings",
        ),
    ] = Redis()
    auth: Annotated[
        Auth,
        Field(description="Authentication settings"),
    ] = Auth()

    model_config = SettingsConfigDict(env_prefix="C2C__", env_nested_delimiter="__")


settings = Settings()
