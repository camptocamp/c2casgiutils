from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings, extra="ignore"):
    """Application settings."""

    # GitHub authentication settings
    AUTH_SECRET: str = ""
    AUTH_COOKIE: str = "c2c-auth"
    AUTH_GITHUB_REPOSITORY: str = ""
    AUTH_GITHUB_ACCESS_TYPE: str = "pull"
    AUTH_GITHUB_AUTH_URL: str = "https://github.com/login/oauth/authorize"
    AUTH_GITHUB_TOKEN_URL: str = "https://github.com/login/oauth/access_token"  # noqa: S105
    AUTH_GITHUB_USER_URL: str = "https://api.github.com/user"
    AUTH_GITHUB_REPO_URL: str = "https://api.github.com/repos"
    AUTH_GITHUB_CLIENT_ID: str = ""
    AUTH_GITHUB_CLIENT_SECRET: str = ""
    AUTH_GITHUB_SCOPE: str = "repo"
    AUTH_GITHUB_SECRET: str = ""
    AUTH_GITHUB_PROXY_URL: str = ""
    AUTH_SESSION_COOKIE: str = "c2c-session"
    AUTH_SESSION_SECRET: str = ""
    AUTH_COOKIE_AGE: int = 7 * 24 * 3600

    model_config = SettingsConfigDict(env_prefix="C2C_")


settings = Settings()
