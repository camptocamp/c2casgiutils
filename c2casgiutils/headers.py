import base64
import ipaddress
import logging
import re
import secrets
from collections.abc import Awaitable, Callable, Collection
from typing import Literal, TypedDict
from urllib.parse import urlsplit

from pydantic import BaseModel
from starlette.datastructures import MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

_LOGGER = logging.getLogger(__name__)

# Content type matcher
_HTML_CONTENT_TYPE_MATCH = r"^text/html(?:;|$)"

Header = str | list[str] | dict[str, str] | dict[str, list[str]] | None

# Placeholder that will be replaced with a generated nonce random value.
CSP_NONCE = "'nonce'"

_ALLOWED_PROTO = {"http", "https", "ws", "wss"}
_DEFAULT_PORT_BY_SCHEME = {"http": 80, "https": 443, "ws": 80, "wss": 443}


def _parse_raw_hosts(value: str) -> list[str]:
    return [item for item in (part.strip() for part in value.split(",")) if item]


class _TrustedHosts:
    """Container for trusted hosts and networks."""

    def __init__(self, trusted_hosts: list[str] | str) -> None:
        self.always_trust: bool = trusted_hosts in ("*", ["*"])

        self.trusted_literals: set[str] = set()
        self.trusted_hosts: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
        self.trusted_networks: set[ipaddress.IPv4Network | ipaddress.IPv6Network] = set()

        if not self.always_trust:
            if isinstance(trusted_hosts, str):
                trusted_hosts = _parse_raw_hosts(trusted_hosts)

            for host in trusted_hosts:
                if "/" in host:
                    try:
                        self.trusted_networks.add(ipaddress.ip_network(host))
                    except ValueError:
                        self.trusted_literals.add(host)
                else:
                    try:
                        self.trusted_hosts.add(ipaddress.ip_address(host))
                    except ValueError:
                        self.trusted_literals.add(host)

    def __contains__(self, host: str | None) -> bool:
        """Check if a client host is trusted."""
        if self.always_trust:
            return True

        if not host:
            return False

        try:
            ip = ipaddress.ip_address(host)
            if ip in self.trusted_hosts:
                return True
            return any(ip in net for net in self.trusted_networks)

        except ValueError:
            return host in self.trusted_literals


def _first_csv_header_value(value: str | None) -> str | None:
    if value is None:
        return None
    first_value = value.split(",", 1)[0].strip()
    return first_value or None


def _unquote_header_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] == '"':
        return stripped[1:-1]
    return stripped


def _parse_forwarded_header(value: str | None) -> dict[str, str]:
    if value is None:
        return {}
    first_item = _first_csv_header_value(value)
    if first_item is None:
        return {}

    result: dict[str, str] = {}
    for part in first_item.split(";"):
        key, separator, raw_val = part.partition("=")
        if not separator:
            continue
        normalized_key = key.strip().lower()
        normalized_value = _unquote_header_value(raw_val)
        if normalized_key and normalized_value:
            result[normalized_key] = normalized_value
    return result


def _split_host_port(host_value: str) -> tuple[str | None, int | None]:
    try:
        parsed = urlsplit(f"//{host_value}")
    except ValueError:
        return None, None
    else:
        return parsed.hostname, parsed.port


def _format_host_header(host: str, port: int | None, scheme: str) -> str:
    host_header = f"[{host}]" if ":" in host and not host.startswith("[") else host
    default_port = _DEFAULT_PORT_BY_SCHEME.get(scheme)
    if port is not None and port != default_port:
        return f"{host_header}:{port}"
    return host_header


class ForwardedHeadersMiddleware:
    """Apply trusted proxy host/proto/port headers to ASGI scope.

    Uvicorn's proxy middleware updates scheme and client address but does not rewrite
    the host used by Starlette/FastAPI absolute URL generation. This middleware updates
    `scope["scheme"]`, `scope["server"]`, and `Host` from trusted `Forwarded` or
    `X-Forwarded-*` headers.
    """

    def __init__(
        self,
        app: ASGIApp,
        trusted_hosts: list[str] | str = "127.0.0.1",
        headers_type: Literal["x-forwarded", "forwarded"] = "x-forwarded",
    ) -> None:
        self.app = app
        self.trusted_hosts = _TrustedHosts(trusted_hosts)
        self.headers_type = headers_type

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Apply trusted forwarded headers before calling the downstream app."""
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        if self.headers_type not in ("forwarded", "x-forwarded"):
            if self.headers_type != "none":  # type: ignore[comparison-overlap]
                _LOGGER.warning(
                    "Invalid headers_type '%s' for ForwardedHeadersMiddleware; expected 'forwarded', 'x-forwarded', or 'none'. No headers will be processed.",
                    self.headers_type,
                )
            await self.app(scope, receive, send)
            return

        client_addr = scope.get("client")
        client_host = client_addr[0] if client_addr else None
        if client_host not in self.trusted_hosts:
            _LOGGER.debug(
                "Client host '%s' not in trusted hosts; skipping forwarded header processing.",
                client_host,
            )
            await self.app(scope, receive, send)
            return

        headers = MutableHeaders(scope=scope)

        host: str | None = None
        port: int | None = None
        scheme = scope.get("scheme", "http")
        forwarded_scheme: str | None = None
        forwarded_host: str | None = None
        x_forwarded_port: str | None = None

        if self.headers_type == "forwarded":
            forwarded = (
                _parse_forwarded_header(headers.get("forwarded")) if self.headers_type == "forwarded" else {}
            )
            forwarded_scheme = forwarded.get("proto")
            forwarded_host = forwarded.get("host")
        else:
            forwarded_scheme = _first_csv_header_value(headers.get("x-forwarded-proto"))
            forwarded_host = _first_csv_header_value(headers.get("x-forwarded-host"))
            x_forwarded_port = _first_csv_header_value(headers.get("x-forwarded-port"))

        if forwarded_scheme:
            forwarded_scheme = forwarded_scheme.lower()
        if forwarded_scheme and forwarded_scheme in _ALLOWED_PROTO:
            if scope["type"] == "websocket":
                scope["scheme"] = forwarded_scheme.replace("http", "ws")
            else:
                scope["scheme"] = forwarded_scheme
            scheme = scope["scheme"]

        if forwarded_host:
            host, port = _split_host_port(forwarded_host)

        if port is None and x_forwarded_port and x_forwarded_port.isdigit():
            port = int(x_forwarded_port)

        if host is not None:
            if port is None:
                port = _DEFAULT_PORT_BY_SCHEME.get(scheme, 80)

            scope["server"] = (host, port)
            headers["host"] = _format_host_header(host, port, scheme)

        await self.app(scope, receive, send)


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
                path,
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
