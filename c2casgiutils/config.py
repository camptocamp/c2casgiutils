# Copyright (c) 2025-2026, Camptocamp SA
import datetime
import logging
import os
import re
from enum import StrEnum
from fractions import Fraction
from typing import Annotated, Any, Literal, cast

import anyio
import yaml
from pydantic import BaseModel, BeforeValidator, Field, GetCoreSchemaHandler, field_validator, model_validator
from pydantic_core import CoreSchema, core_schema
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_LOGGER = logging.getLogger(__name__)


class Redis(BaseModel):
    """Redis configuration."""

    url: Annotated[
        str | None,
        Field(
            description="Redis connection URL",
        ),
    ] = None
    options: Annotated[
        dict[str, Any],
        NoDecode,
        Field(description="Redis connection options, e.g. 'socket_timeout=5,ssl=True'."),
    ] = {}

    @field_validator("options", mode="before")
    @classmethod
    def parse_options(cls, value: str | dict[str, Any] | None) -> dict[str, Any]:
        """Parse the options string into a dictionary."""
        if value is None or isinstance(value, dict):
            return value or {}
        return {
            e[: e.index("=")]: yaml.safe_load(e[e.index("=") + 1 :]) for e in value.split(",") if e.strip()
        }

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
    broadcast_prefix: Annotated[
        str,
        Field(
            description="Redis prefix for broadcast channels",
        ),
    ] = "broadcast_api_"


class Prometheus(BaseModel):
    """Prometheus configuration."""

    prefix: Annotated[
        str,
        Field(
            description="Prefix for Prometheus metrics",
        ),
    ] = "c2casgiutils_"
    port: Annotated[int, Field(description="Port for Prometheus metrics")] = 9000


def parse_comma_separated_list(value: str | list[str] | None) -> list[str]:
    """Parse a comma-separated string into a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [v.strip() for v in value if v.strip()]
    return [v.strip() for v in value.split(",") if v.strip()]


def parse_comma_separated_int_list(value: str | list[int] | None) -> list[int]:
    """Parse a comma-separated string into a list of ints."""
    if value is None:
        return []
    if isinstance(value, list):
        return [int(v) for v in value]
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def parse_comma_separated_float_list(value: str | list[float] | None) -> list[float]:
    """Parse a comma-separated string into a list of floats."""
    if value is None:
        return []
    if isinstance(value, list):
        return [float(v) for v in value]
    return [float(v.strip()) for v in value.split(",") if v.strip()]


StringList = Annotated[list[str], NoDecode, BeforeValidator(parse_comma_separated_list)]
IntList = Annotated[list[int], NoDecode, BeforeValidator(parse_comma_separated_int_list)]
FloatList = Annotated[list[float], NoDecode, BeforeValidator(parse_comma_separated_float_list)]


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
    ignore_errors: Annotated[StringList, Field(description="List of exception class names to ignore")] = []
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
    project_root: Annotated[str, Field(description="Root directory of the project")] = (
        # `pathlib` is not allowed by the project rules and this default is computed synchronously.
        os.getcwd()  # noqa: PTH109
    )
    in_app_include: Annotated[
        StringList,
        Field(description="List of module prefixes that are in the app"),
    ] = []
    in_app_exclude: Annotated[
        StringList,
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
            description=(
                "Default tags for Sentry events, loaded from environment variables with prefix "
                "`C2C__SENTRY__TAG_` to set tags. The tag name will be the part after the prefix, "
                "converted to lowercase. For example, `C2C__SENTRY__TAG_SERVICE=my-service` will set a tag "
                "named `service` (lowercase) with value `my-service`."
            ),
        ),
    ] = {}

    @model_validator(mode="after")
    def build_sentry_tags(self) -> "Sentry":
        """Build the tags dictionary from environment variables."""
        # Get all environment variables that start with "C2C__SENTRY__TAG_"
        prefix = "C2C__SENTRY__TAG_"
        self.tags = {
            key[len(prefix) :].lower(): value for key, value in os.environ.items() if key.startswith(prefix)
        }
        return self


class _IsoTimedelta(datetime.timedelta):
    def __str__(self) -> str:
        total_seconds = int(self.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if hours > 0:
            parts.append(f"{hours}H")
        if minutes > 0:
            parts.append(f"{minutes}M")
        if seconds > 0:
            parts.append(f"{seconds}S")

        return f"PT{''.join(parts)}" if parts else "PT0S"


_ISO_DURATION_RE = re.compile(
    r"^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$",
)


def _unit_to_name(unit: str) -> str:
    return {"w": "weeks", "d": "days", "h": "hours", "m": "minutes", "s": "seconds"}[unit]


def _next_unit(unit: str) -> str:
    order = ["w", "d", "h", "m", "s"]
    idx = order.index(unit)
    return _unit_to_name(order[idx + 1]) if idx + 1 < len(order) else "seconds"


def parse_duration(text: str | datetime.timedelta) -> datetime.timedelta:
    """
    Parse a duration string to a timedelta.

    Supports ISO 8601 duration format (e.g. PT3H, P30D, PT600S) and
    the short format (e.g. 2h30, 2m30, 1d, 1w, 1w2d3h4m5s).
    The supported units are: w (weeks), d (days), h (hours), m (minutes), s (seconds).
    When the last number has no unit, it takes the next logical unit
    (e.g. 2h30 = 2h30m, 2m30 = 2m30s).
    A plain number string (e.g. "300") is treated as seconds.
    """
    if isinstance(text, datetime.timedelta):
        return text
    match = _ISO_DURATION_RE.match(text)
    if match:
        parts = match.groups()
        return datetime.timedelta(
            days=int(parts[2] or 0),
            hours=int(parts[3] or 0),
            minutes=int(parts[4] or 0),
            seconds=float(parts[5] or 0),
        )
    segments = re.findall(r"(\d+)([wdhms])?", text)
    if segments:
        kwargs: dict[str, int] = {}
        last_unit = "s"
        for value, unit in segments:
            if unit:
                kwargs.setdefault(_unit_to_name(unit), int(value))
                last_unit = unit
            else:
                kwargs.setdefault(_next_unit(last_unit), int(value))
        return datetime.timedelta(**kwargs)
    message = f"Invalid time delta: {text}"
    raise ValueError(message)


Duration = Annotated[datetime.timedelta, BeforeValidator(parse_duration)]


# Exponent of the decimal (SI) prefixes, see:
# https://fr.wikipedia.org/wiki/Pr%C3%A9fixes_du_Syst%C3%A8me_international_d%27unit%C3%A9s
# `K` is not an SI symbol (kilo is `k`) but is accepted as a widely used alias.
_SI_DECIMAL_PREFIXES: dict[str, int] = {
    "Q": 30,  # quetta
    "R": 27,  # ronna
    "Y": 24,  # yotta
    "Z": 21,  # zetta
    "E": 18,  # exa
    "P": 15,  # peta
    "T": 12,  # tera
    "G": 9,  # giga
    "M": 6,  # mega
    "k": 3,  # kilo
    "K": 3,  # kilo (non-SI alias)
    "h": 2,  # hecto
    "da": 1,  # deca
    "": 0,  # no prefix
    "d": -1,  # deci
    "c": -2,  # centi
    "m": -3,  # milli
    "\u00b5": -6,  # micro (MICRO SIGN)
    "\u03bc": -6,  # micro (GREEK SMALL LETTER MU)
    "u": -6,  # micro (ASCII alias)
    "n": -9,  # nano
    "p": -12,  # pico
    "f": -15,  # femto
    "a": -18,  # atto
    "z": -21,  # zepto
    "y": -24,  # yocto
    "r": -27,  # ronto
    "q": -30,  # quecto
}

# Exponent of the binary (IEC 60027-2) prefixes, the base is 1024 instead of 10.
_SI_BINARY_PREFIXES: dict[str, int] = {
    "Ki": 1,  # kibi
    "ki": 1,  # kibi (non-IEC alias)
    "Mi": 2,  # mebi
    "Gi": 3,  # gibi
    "Ti": 4,  # tebi
    "Pi": 5,  # pebi
    "Ei": 6,  # exbi
    "Zi": 7,  # zebi
    "Yi": 8,  # yobi
}

# Sorted by descending length to match the two letters prefix `da` before the one letter prefix `d`,
# the empty prefix is not part of the pattern.
_SI_DECIMAL_PATTERN = "|".join(
    re.escape(prefix) for prefix in sorted(_SI_DECIMAL_PREFIXES, key=len, reverse=True) if prefix
)
_SI_UNIT_RE = re.compile(rf"^([+-]?\d+(?:\.\d+)?)({_SI_DECIMAL_PATTERN})?(i)?([a-zA-Z]?)$")


def _parse_si_unit(text: str | float) -> Fraction:
    """
    Parse an SI unit string to an exact fraction.

    See `parse_si_unit` for the supported syntax.
    """
    if not isinstance(text, str):
        # Also covers int, Fraction and Decimal inputs.
        return Fraction(text)
    match = _SI_UNIT_RE.match(text.strip())
    if not match:
        message = f"Invalid SI unit: {text}"
        raise ValueError(message)
    value = Fraction(match.group(1))
    prefix = match.group(2) or ""
    if match.group(3):
        if not prefix:
            message = f"Invalid binary SI unit prefix: {text}"
            raise ValueError(message)
        binary_exponent = _SI_BINARY_PREFIXES.get(f"{prefix}i")
        if binary_exponent is None:
            message = f"Invalid binary SI unit prefix: {text}"
            raise ValueError(message)
        return value * Fraction(1024) ** binary_exponent
    return value * Fraction(10) ** _SI_DECIMAL_PREFIXES[prefix]


def parse_si_unit(text: str | float) -> float:
    """
    Parse an SI unit string to a float.

    The value is a number optionally followed by an SI prefix, optionally followed by the binary
    marker `i`, optionally followed by a single unit letter that is ignored (`B`, `o`, ...).

    All the SI decimal prefixes are supported and are case sensitive:
    `Q` (quetta), `R` (ronna), `Y` (yotta), `Z` (zetta), `E` (exa), `P` (peta), `T` (tera),
    `G` (giga), `M` (mega), `k` (kilo), `h` (hecto), `da` (deca), `d` (deci), `c` (centi),
    `m` (milli), `µ`/`μ`/`u` (micro), `n` (nano), `p` (pico), `f` (femto), `a` (atto),
    `z` (zepto), `y` (yocto), `r` (ronto), `q` (quecto).
    `K` is also accepted as a non-SI alias of `k` (kilo).

    The binary (IEC) prefixes are supported by adding an `i` after the prefix, they use a base
    of 1024 instead of 10: `Ki` (kibi), `Mi` (mebi), `Gi` (gibi), `Ti` (tebi), `Pi` (pebi),
    `Ei` (exbi), `Zi` (zebi), `Yi` (yobi).

    Note that the decimal prefixes are case sensitive, `10M` is 10'000'000 (mega) while
    `10m` is 0.01 (milli).

    Examples: 1000, 1k, 1KiB, 10M, 1.5G, 2Go, 500MiB, 5cm, 1da, 3µs

    Note that Pydantic does not validate the default values, a default must be wrapped in
    `parse_si_unit(...)` to be a float, e.g.: `= parse_si_unit("100M")`.
    """
    return float(_parse_si_unit(text))


def parse_si_unit_int(text: str | float) -> int:
    """
    Parse an SI unit string to an int.

    See `parse_si_unit` for the supported syntax. The result is rounded to the nearest integer
    (Python's banker's rounding), e.g. `1.5K` gives 1500 and `1.5m` gives 0.

    Note that Pydantic does not validate the default values, a default must be wrapped in
    `parse_si_unit_int(...)` to be an int, e.g.: `= parse_si_unit_int("100M")`.
    """
    return round(_parse_si_unit(text))


SiUnit = Annotated[float, BeforeValidator(parse_si_unit)]
SiUnitInt = Annotated[int, BeforeValidator(parse_si_unit_int)]


def parse_path(value: str | os.PathLike[str]) -> anyio.Path:
    """
    Convert a string or any path-like object to an `anyio.Path`.

    Note that Pydantic does not validate the default values, a default must be wrapped in
    `parse_path(...)` to be an `anyio.Path`, e.g.: `= parse_path("/app/templates")`.
    """
    if isinstance(value, anyio.Path):
        # Avoid creating a new wrapper around an already existing `anyio.Path`.
        return value
    return anyio.Path(value)


class _AnyioPathAnnotation:
    """Pydantic annotation that validates the values into an `anyio.Path`."""

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: GetCoreSchemaHandler) -> CoreSchema:
        """Build the Pydantic core schema of the `Path` type."""
        return core_schema.no_info_after_validator_function(
            parse_path,
            # `os.PathLike` covers `pathlib.Path` and `anyio.Path`.
            core_schema.union_schema([core_schema.str_schema(), core_schema.is_instance_schema(os.PathLike)]),
            serialization=core_schema.plain_serializer_function_ser_schema(str, when_used="always"),
        )


Path = Annotated[anyio.Path, _AnyioPathAnnotation()]
"""Path type that is validated into an `anyio.Path` and serialized as a string."""


class GitHubAccessType(StrEnum):
    """GitHub access type for repository permissions."""

    PULL = "pull"
    PUSH = "push"
    ADMIN = "admin"


class AuthGitHub(BaseModel):
    """GitHub Authentication settings."""

    repository: Annotated[
        str | None,
        Field(description="GitHub repository for authentication"),
    ] = None
    access_type_read_only: Annotated[
        GitHubAccessType,
        Field(description="GitHub access type required for read-only operations"),
    ] = GitHubAccessType.PULL
    access_type_read_write: Annotated[
        GitHubAccessType,
        Field(description="GitHub access type required for read-write operations"),
    ] = GitHubAccessType.PUSH
    access_type_admin: Annotated[
        GitHubAccessType,
        Field(description="GitHub access type required for admin operations"),
    ] = GitHubAccessType.ADMIN
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
        Duration,
        Field(description="GitHub state cookie age (default: 10 minutes)"),
    ] = _IsoTimedelta(minutes=10)
    access_token_expiration_margin: Annotated[
        Duration,
        Field(
            description=(
                "Safety margin applied before checking GitHub access token expiration. "
                "Accepts ISO 8601 durations (e.g.: `PT1M`), short format (e.g.: `10m`), or seconds (e.g.: `300`)."
            ),
        ),
    ] = _IsoTimedelta(minutes=1)

    @field_validator("access_token_expiration_margin")
    @classmethod
    def validate_access_token_expiration_margin(cls, value: datetime.timedelta) -> datetime.timedelta:
        """Validate that access_token_expiration_margin is not negative."""
        if value < datetime.timedelta(0):
            message = "C2C__AUTH__GITHUB__ACCESS_TOKEN_EXPIRATION_MARGIN must be >= PT0S"
            raise ValueError(message)
        return value


class AuthJWTCookie(BaseModel):
    """JWT cookie settings."""

    name: Annotated[str, Field(description="Authentication cookie name")] = "c2c-jwt-auth"
    age: Annotated[
        Duration,
        Field(description="Authentication cookie age (default: 7 days)"),
    ] = _IsoTimedelta(days=7)
    same_site: Annotated[
        Literal["lax", "strict", "none"],
        Field(
            description=(
                "SameSite attribute for the JWT cookies (state and auth token). "
                "Defaults to 'lax' to support OAuth and other redirect-based login flows that rely "
                "on the cookie being sent on top-level navigation from external sites. "
                "Use 'strict' for stronger CSRF protection when such flows are not required."
            ),
        ),
    ] = "lax"
    secure: Annotated[
        bool,
        Field(
            description="Whether the JWT cookie should be secure",
        ),
    ] = True
    path: Annotated[
        str | None,
        Field(
            description="Path for the JWT cookie (default: the c2c index path)",
        ),
    ] = None

    @field_validator("same_site", mode="before")
    @classmethod
    def normalize_same_site(cls, value: str | None) -> Literal["lax", "strict", "none"]:
        """Normalize same_site values like `Lax` to lowercase."""
        if value is None:
            message = "C2C__AUTH__JWT__COOKIE__SAME_SITE environment variable should be defined"
            raise ValueError(message)
        result = value.lower()
        if result in {"lax", "strict", "none"}:
            return cast("Literal['lax', 'strict', 'none']", result)
        message = f"Invalid C2C__AUTH__JWT__COOKIE__SAME_SITE environment variable value: {value}"
        raise ValueError(message)


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


class ProxyHeaders(BaseModel):
    """Proxy headers handling settings."""

    type: Annotated[
        Literal["none", "x-forwarded", "forwarded"],
        Field(
            description=(
                "Proxy headers mode: 'none' disables host/proto rewriting, "
                "'x-forwarded' trusts X-Forwarded-* headers, 'forwarded' trusts RFC7239 Forwarded header"
            ),
        ),
    ] = "none"
    trusted_hosts: Annotated[
        StringList,
        Field(
            description=(
                "Trusted proxy client hosts/networks. Accepts comma-separated string or list "
                "(e.g. '127.0.0.1,10.0.0.0/8' or '*')."
            ),
        ),
    ] = ["127.0.0.1"]


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
    proxy_headers: Annotated[
        ProxyHeaders,
        Field(description="Proxy headers handling settings"),
    ] = ProxyHeaders()
    http: Annotated[
        bool,
        Field(
            description="The application is running in HTTP mode to be used for development only (default: False)",
        ),
    ] = False
    route_prefix: Annotated[
        str, Field(description="Route prefix for the application, should start and end with a '/'")
    ] = "/"

    model_config = SettingsConfigDict(env_prefix="C2C__", env_nested_delimiter="__")

    @model_validator(mode="after")
    def validate_route_prefix(self) -> "Settings":
        """Ensure route_prefix has leading and trailing slashes."""
        prefix = (self.route_prefix or "").strip()
        if not prefix:
            prefix = "/"
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        if not prefix.endswith("/"):
            prefix = f"{prefix}/"
        if prefix != self.route_prefix:
            _LOGGER.info("Normalized route prefix to '%s'", prefix)
        self.route_prefix = prefix
        return self


settings = Settings()
