import logging
import re
from collections.abc import Awaitable, Callable, Collection
from typing import TypedDict

from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_LOGGER = logging.getLogger(__name__)

Header = str | list[str] | dict[str, str] | dict[str, list[str]] | None


class HeaderMatcher(TypedDict, total=False):
    """Model to match headers."""

    netloc_match: str | None
    path_match: str | None
    headers: dict[str, Header]
    status_code: int | tuple[int, int] | None
    order: int
    methods: list[str] | None


class _HeaderMatcherBuild(BaseModel):
    """Model to match headers."""

    name: str
    netloc_match: re.Pattern[str] | None
    path_match: re.Pattern[str] | None
    headers: dict[str, str | None]
    status_code: int | tuple[int, int] | None
    methods: list[str] | None


def _build_header(
    value: Header,
    separator: str = "; ",
    dict_separator: str = "=",
    final_separator: bool = False,
) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        result = separator.join(value)
        if result and final_separator:
            return result + separator
        return result
    if isinstance(value, dict):
        values = []
        for key, val in value.items():
            if isinstance(val, str):
                values.append(f"{key}{dict_separator}{val}")
            elif isinstance(val, list):
                values.append(f"{key}{dict_separator}{' '.join(val)}")
            else:
                message = f"Unsupported value type for header '{key}': {type(val)}. Expected str or list."
                raise TypeError(message)
        result = separator.join(values)
        if result and final_separator:
            return result + separator
        return result

    message = f"Unsupported header type: {type(value)}. Expected str, list, or dict."
    raise TypeError(message)


DEFAULT_HEADERS_CONFIG: dict[str, HeaderMatcher] = {
    "default": {
        "headers": {
            "Content-Security-Policy": {"default-src": ["'self'"]},
            "X-Frame-Options": "DENY",
            "Strict-Transport-Security": [f"max-age={86400 * 365}", "includeSubDomains", "preload"],
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": ["geolocation=()", "microphone=()"],
            "X-DNS-Prefetch-Control": "off",
            "Expect-CT": "max-age=86400, enforce",
            "Origin-Agent-Cluster": "?1",
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin",
        },
        "order": -1,
    },
    "localhost": {  # Special case for localhost
        "netloc_match": r"^localhost(:\d+)?$",
        "headers": {
            "Strict-Transport-Security": None,
        },
    },
    "c2c": {  # Special case for c2c
        "path_match": r"^c2c/?$",
        "headers": {
            "Content-Security-Policy": {
                "default-src": ["'self'"],
                "script-src-elem": [
                    "'self'",
                    "https://cdnjs.cloudflare.com/ajax/libs/bootstrap/",
                    "https://cdn.jsdelivr.net/npm/@sbrunner/",
                ],
                "style-src-elem": [
                    "'self'",
                    "https://cdnjs.cloudflare.com/ajax/libs/bootstrap/",
                ],
                "style-src-attr": [
                    "'unsafe-inline'",  # Required by Lit
                ],
            },
        },
        "status_code": 200,
    },
    "docs": {  # Special case for documentation
        "path_match": r"^(.*/)?docs/?$",
        "headers": {
            "Content-Security-Policy": {
                "default-src": [
                    "'self'",
                ],
                "script-src-elem": [
                    "'self'",
                    "'unsafe-inline'",
                    "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/",
                ],
                "style-src-elem": [
                    "'self'",
                    "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/",
                ],
                "img-src": [
                    "'self'",
                    "data:",
                    "https://fastapi.tiangolo.com/img/",
                ],
            },
            "Cross-Origin-Embedder-Policy": None,
        },
        "status_code": 200,
    },
    "redoc": {  # Special case for Redoc
        "path_match": r"^(.*/)?redoc/?$",
        "headers": {
            "Content-Security-Policy": {
                "default-src": [
                    "'self'",
                ],
                "script-src-elem": [
                    "'self'",
                    "'unsafe-inline'",
                    "https://cdn.jsdelivr.net/npm/redoc@2/",
                ],
                "style-src-elem": [
                    "'self'",
                    "'unsafe-inline'",
                    "https://fonts.googleapis.com/css",
                ],
                "img-src": [
                    "'self'",
                    "data:",
                    "https://fastapi.tiangolo.com/img/",
                    "https://cdn.redoc.ly/redoc/",
                ],
                "font-src": [
                    "'self'",
                    " https://fonts.gstatic.com/s/",
                ],
                "worker-src": [
                    "'self'",
                    "blob:",
                ],
            },
            "Cross-Origin-Embedder-Policy": None,
        },
    },
}


class ArmorHeaderMiddleware(BaseHTTPMiddleware):
    """Middleware to add headers to responses based on request netloc (host:port) and path."""

    def __init__(
        self,
        app: ASGIApp,
        headers_config: dict[str, HeaderMatcher] | None = None,
        use_default: bool = True,
    ) -> None:
        """Initialize the HeaderMiddleware."""
        if headers_config is None:
            headers_config = {}

        default_headers_config_ordered: Collection[tuple[str, HeaderMatcher]] = (
            DEFAULT_HEADERS_CONFIG.items() if use_default else []
        )
        headers_config_ordered: list[tuple[str, HeaderMatcher]] = sorted(
            [*default_headers_config_ordered, *headers_config.items()],
            key=lambda x: x[1].get("order", 0),
        )

        self.headers_config: list[_HeaderMatcherBuild] = []

        for name, config in headers_config_ordered:
            netloc_match_str = config.get("netloc_match")
            netloc_match = re.compile(netloc_match_str) if netloc_match_str is not None else None
            path_match_str = config.get("path_match")
            path_match = re.compile(path_match_str) if path_match_str is not None else None
            headers = {}
            for header, value in config["headers"].items():
                if header == "Content-Security-Policy":
                    headers[header] = _build_header(value, dict_separator=" ", final_separator=True)
                elif header == "Permissions-Policy":
                    headers[header] = _build_header(value, separator=", ")
                else:
                    headers[header] = _build_header(value)
            self.headers_config.append(
                _HeaderMatcherBuild(
                    name=name,
                    netloc_match=netloc_match,
                    path_match=path_match,
                    headers=headers,
                    status_code=config.get("status_code"),
                    methods=config.get("methods"),
                ),
            )
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Dispatch the request and add headers to the response."""
        response = await call_next(request)

        netloc = request.base_url.netloc
        path = request.url.path[len(request.base_url.path) :]

        for config in self.headers_config:
            if config.netloc_match and not config.netloc_match.match(netloc):
                continue
            if config.path_match and not config.path_match.match(path):
                continue
            if config.status_code is not None:
                if isinstance(config.status_code, tuple):
                    if (
                        response.status_code < config.status_code[0]
                        or response.status_code > config.status_code[1]
                    ):
                        continue
                elif response.status_code != config.status_code:
                    continue
            if config.methods is not None and request.method not in config.methods:
                continue
            _LOGGER.debug(
                "Adding headers for %s on %s",
                config.name,
                request.url.path,
            )
            for header, value in config.headers.items():
                if value is None:
                    if header in response.headers:
                        del response.headers[header]
                else:
                    response.headers[header] = value

        return response
