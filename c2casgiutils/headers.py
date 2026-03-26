import base64
import logging
import re
import secrets
from collections.abc import Awaitable, Callable, Collection
from typing import TypedDict

from pydantic import BaseModel
from starlette.datastructures import URL
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

_LOGGER = logging.getLogger(__name__)

# Content type matcher
_HTML_CONTENT_TYPE_MATCH = r"^text/html(?:;|$)"
_LOCALHOST_NETLOC_RE = re.compile(r"^localhost(:\d+)?$")

Header = str | list[str] | dict[str, str] | dict[str, list[str]] | None

# Placeholder that will be replaced with a generated nonce random value.
CSP_NONCE = "'nonce'"


class HeaderMatcher(TypedDict, total=False):
    """Model to match headers."""

    netloc_match: str | None
    path_match: str | None
    content_type_match: str | None
    headers: dict[str, Header]
    status_code: int | tuple[int, int] | None
    order: int
    methods: list[str] | None


class _HeaderMatcherBuild(BaseModel):
    """Model to match headers."""

    name: str
    netloc_match: re.Pattern[str] | None
    path_match: re.Pattern[str] | None
    content_type_match: re.Pattern[str] | None
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
        "content_type_match": _HTML_CONTENT_TYPE_MATCH,
        "headers": {
            "Strict-Transport-Security": None,
        },
    },
    "c2c": {  # Special case for c2c
        "path_match": r"^(.*/)?c2c/?$",
        "content_type_match": _HTML_CONTENT_TYPE_MATCH,
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
        "content_type_match": _HTML_CONTENT_TYPE_MATCH,
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
    },
    "redoc": {  # Special case for Redoc
        "path_match": r"^(.*/)?redoc/?$",
        "content_type_match": _HTML_CONTENT_TYPE_MATCH,
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


class HTTPSRedirectMiddleware:
    r"""
    Middleware that redirects HTTP requests to HTTPS and WebSocket requests to WSS.

    Requests from ``localhost`` (matching ``^localhost(:\d+)?$``) are passed through
    without a redirect so that Kubernetes liveness/readiness probes sent over plain HTTP
    continue to work even when HTTPS enforcement is enabled.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the middleware."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle ASGI requests, redirecting HTTP to HTTPS and WS to WSS unless the host is localhost."""
        if scope["type"] in ("http", "websocket"):
            url = URL(scope=scope)
            if not _LOCALHOST_NETLOC_RE.match(url.netloc):
                # Map schemes: http -> https, ws -> wss
                scheme_map = {"http": "https", "ws": "wss"}
                new_scheme = scheme_map.get(url.scheme)
                if new_scheme:
                    redirect_url = url.replace(scheme=new_scheme)
                    response = RedirectResponse(url=str(redirect_url), status_code=307)
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


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
            content_type_match_str = config.get("content_type_match")
            content_type_match = (
                re.compile(content_type_match_str, re.IGNORECASE)
                if content_type_match_str is not None
                else None
            )
            headers = {}
            for header, value in config["headers"].items():
                if header in ("Content-Security-Policy", "Content-Security-Policy-Report-Only"):
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
                    content_type_match=content_type_match,
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
        netloc = request.base_url.netloc
        path = request.url.path[len(request.base_url.path) :]
        _LOGGER.debug("Processing headers for request netloc: '%s', path: '%s'.", netloc, path)

        used_config = []
        nonce: str | None = None
        for config in self.headers_config:
            if config.netloc_match and not config.netloc_match.match(netloc):
                continue
            if config.path_match and not config.path_match.match(path):
                continue
            if config.methods is not None and request.method not in config.methods:
                continue
            used_config.append(config)
            if nonce is None:
                for header in ("Content-Security-Policy", "Content-Security-Policy-Report-Only"):
                    header_value = config.headers.get(header)
                    if header_value is not None and CSP_NONCE in header_value:
                        # Generate a new nonce
                        nonce = base64.b64encode(secrets.token_bytes(16)).decode("utf-8")
                        request.state.nonce = nonce
                        break

        response = await call_next(request)

        for config in used_config:
            if config.status_code is not None:
                if isinstance(config.status_code, tuple):
                    if (
                        response.status_code < config.status_code[0]
                        or response.status_code > config.status_code[1]
                    ):
                        continue
                elif response.status_code != config.status_code:
                    continue
            if config.content_type_match is not None:
                content_type = response.headers.get("Content-Type")
                if content_type is None or not config.content_type_match.match(content_type):
                    continue
            _LOGGER.debug(
                "Adding headers from '%s' on path '%s'.",
                config.name,
                request.url.path,
            )
            for header, value in config.headers.items():
                if value is None:
                    if header in response.headers:
                        del response.headers[header]
                else:
                    used_value = value
                    if (
                        header in ("Content-Security-Policy", "Content-Security-Policy-Report-Only")
                        and CSP_NONCE in value
                    ):
                        if nonce is None:
                            _LOGGER.warning(
                                "CSP nonce placeholder found in header '%s', but nonce was not generated; "
                                "skipping header for this response.",
                                header,
                            )
                            continue
                        # Replace nonce placeholders
                        used_value = used_value.replace(CSP_NONCE, f"'nonce-{nonce}'")

                    response.headers[header] = used_value

        return response
