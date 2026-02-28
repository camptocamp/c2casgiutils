import base64
import logging
import os
import re
from collections.abc import Awaitable, Callable, Collection
from typing import TypedDict

from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

_LOGGER = logging.getLogger(__name__)

# Headers
HEADER_CONTENT_SECURITY_POLICY = "Content-Security-Policy"
HEADER_CONTENT_SECURITY_POLICY_REPORT_ONLY = "Content-Security-Policy-Report-Only"
HEADER_REPORTING_ENDPOINT = "Reporting-Endpoint"
HEADER_X_FRAME_OPTIONS = "X-Frame-Options"
HEADER_STRICT_TRANSPORT_SECURITY = "Strict-Transport-Security"
HEADER_X_CONTENT_TYPE_OPTIONS = "X-Content-Type-Options"
HEADER_REFERRER_POLICY = "Referrer-Policy"
HEADER_PERMISSIONS_POLICY = "Permissions-Policy"
HEADER_X_DNS_PREFETCH_CONTROL = "X-DNS-Prefetch-Control"
HEADER_EXPECT_CT = "Expect-CT"
HEADER_ORIGIN_AGENT_CLUSTER = "Origin-Agent-Cluster"
HEADER_CROSS_ORIGIN_EMBEDDER_POLICY = "Cross-Origin-Embedder-Policy"
HEADER_CROSS_ORIGIN_OPENER_POLICY = "Cross-Origin-Opener-Policy"
HEADER_CROSS_ORIGIN_RESOURCE_POLICY = "Cross-Origin-Resource-Policy"
# Directive Names
CSP_DEFAULT_SRC = "default-src"
CSP_SCRIPT_SRC = "script-src"
CSP_SCRIPT_SRC_ELEM = "script-src-elem"
CSP_SCRIPT_SRC_ATTR = "script-src-attr"
CSP_STYLE_SRC = "style-src"
CSP_STYLE_SRC_ELEM = "style-src-elem"
CSP_STYLE_SRC_ATTR = "style-src-attr"
CSP_IMG_SRC = "img-src"
CSP_CONNECT_SRC = "connect-src"
CSP_FONT_SRC = "font-src"
CSP_OBJECT_SRC = "object-src"
CSP_MEDIA_SRC = "media-src"
CSP_FRAME_SRC = "frame-src"
CSP_WORKER_SRC = "worker-src"
CSP_MANIFEST_SRC = "manifest-src"
CSP_CHILD_SRC = "child-src"
CSP_FENCED_FRAME_SRC = "fenced-frame-src"
CSP_BASE_URI = "base-uri"
CSP_FORM_ACTION = "form-action"
CSP_FRAME_ANCESTORS = "frame-ancestors"
CSP_REPORT_TO = "report-to"
CSP_REQUIRE_TRUSTED_TYPES_FOR = "require-trusted-types-for"
CSP_SANDBOX = "sandbox"
CSP_TRUSTED_TYPES = "trusted-types"
CSP_UPGRADE_INSECURE_REQUESTS = "upgrade-insecure-requests"
# Special Security Keywords
CSP_NONCE = "'nonce'"
CSP_UNSAFE_INLINE = "'unsafe-inline'"
CSP_UNSAFE_EVAL = "'unsafe-eval'"
CSP_UNSAFE_HASHES = "'unsafe-hashes'"
CSP_STRICT_DYNAMIC = "'strict-dynamic'"
CSP_REPORT_SAMPLE = "'report-sample'"
CSP_TRUSTED_TYPES_EVAL = "'trusted-types-eval'"
CSP_WASM_UNSAFE_EVAL = "'wasm-unsafe-eval'"
CSP_INLINE_SPECULATION_RULES = "'inline-speculation-rules'"
# Source Keywords
CSP_SELF = "'self'"
CSP_NONE = "'none'"
CSP_DATA = "data:"
CSP_BLOB = "blob:"
# Content type matcher
HTML_CONTENT_TYPE_MATCH = r"^text/html(?:;|$)"

Header = str | list[str] | dict[str, str] | dict[str, list[str]] | None


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
            HEADER_CONTENT_SECURITY_POLICY: {CSP_DEFAULT_SRC: [CSP_SELF]},
            HEADER_X_FRAME_OPTIONS: "DENY",
            HEADER_STRICT_TRANSPORT_SECURITY: [f"max-age={86400 * 365}", "includeSubDomains", "preload"],
            HEADER_X_CONTENT_TYPE_OPTIONS: "nosniff",
            HEADER_REFERRER_POLICY: "no-referrer",
            HEADER_PERMISSIONS_POLICY: ["geolocation=()", "microphone=()"],
            HEADER_X_DNS_PREFETCH_CONTROL: "off",
            HEADER_EXPECT_CT: "max-age=86400, enforce",
            HEADER_ORIGIN_AGENT_CLUSTER: "?1",
            HEADER_CROSS_ORIGIN_EMBEDDER_POLICY: "require-corp",
            HEADER_CROSS_ORIGIN_OPENER_POLICY: "same-origin",
            HEADER_CROSS_ORIGIN_RESOURCE_POLICY: "same-origin",
        },
        "order": -1,
    },
    "localhost": {  # Special case for localhost
        "netloc_match": r"^localhost(:\d+)?$",
        "content_type_match": HTML_CONTENT_TYPE_MATCH,
        "headers": {
            HEADER_STRICT_TRANSPORT_SECURITY: None,
        },
    },
    "c2c": {  # Special case for c2c
        "path_match": r"^(.*/)?c2c/?$",
        "content_type_match": HTML_CONTENT_TYPE_MATCH,
        "headers": {
            HEADER_CONTENT_SECURITY_POLICY: {
                CSP_DEFAULT_SRC: [CSP_SELF],
                CSP_SCRIPT_SRC_ELEM: [
                    CSP_SELF,
                    "https://cdnjs.cloudflare.com/ajax/libs/bootstrap/",
                    "https://cdn.jsdelivr.net/npm/@sbrunner/",
                ],
                CSP_STYLE_SRC_ELEM: [
                    CSP_SELF,
                    "https://cdnjs.cloudflare.com/ajax/libs/bootstrap/",
                ],
                CSP_STYLE_SRC_ATTR: [
                    CSP_UNSAFE_INLINE,  # Required by Lit
                ],
            },
        },
        "status_code": 200,
    },
    "docs": {  # Special case for documentation
        "path_match": r"^(.*/)?docs/?$",
        "content_type_match": HTML_CONTENT_TYPE_MATCH,
        "headers": {
            HEADER_CONTENT_SECURITY_POLICY: {
                CSP_DEFAULT_SRC: [
                    CSP_SELF,
                ],
                CSP_SCRIPT_SRC_ELEM: [
                    CSP_SELF,
                    CSP_UNSAFE_INLINE,
                    "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/",
                ],
                CSP_STYLE_SRC_ELEM: [
                    CSP_SELF,
                    "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/",
                ],
                CSP_IMG_SRC: [
                    CSP_SELF,
                    CSP_DATA,
                    "https://fastapi.tiangolo.com/img/",
                ],
            },
            HEADER_CROSS_ORIGIN_EMBEDDER_POLICY: None,
        },
    },
    "redoc": {  # Special case for Redoc
        "path_match": r"^(.*/)?redoc/?$",
        "content_type_match": HTML_CONTENT_TYPE_MATCH,
        "headers": {
            HEADER_CONTENT_SECURITY_POLICY: {
                CSP_DEFAULT_SRC: [
                    CSP_SELF,
                ],
                CSP_SCRIPT_SRC_ELEM: [
                    CSP_SELF,
                    CSP_UNSAFE_INLINE,
                    "https://cdn.jsdelivr.net/npm/redoc@2/",
                ],
                CSP_STYLE_SRC_ELEM: [
                    CSP_SELF,
                    CSP_UNSAFE_INLINE,
                    "https://fonts.googleapis.com/css",
                ],
                CSP_IMG_SRC: [
                    CSP_SELF,
                    CSP_DATA,
                    "https://fastapi.tiangolo.com/img/",
                    "https://cdn.redoc.ly/redoc/",
                ],
                CSP_FONT_SRC: [
                    CSP_SELF,
                    "https://fonts.gstatic.com/s/",
                ],
                CSP_WORKER_SRC: [
                    CSP_SELF,
                    CSP_BLOB,
                ],
            },
            HEADER_CROSS_ORIGIN_EMBEDDER_POLICY: None,
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
                if header in (HEADER_CONTENT_SECURITY_POLICY, HEADER_CONTENT_SECURITY_POLICY_REPORT_ONLY):
                    headers[header] = _build_header(value, dict_separator=" ", final_separator=True)
                elif header == HEADER_PERMISSIONS_POLICY:
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
                for header in (HEADER_CONTENT_SECURITY_POLICY, HEADER_CONTENT_SECURITY_POLICY_REPORT_ONLY):
                    header_value = config.headers.get(header)
                    if header_value is not None and CSP_NONCE in header_value:
                        # Generate a new nonce
                        nonce = base64.b64encode(os.urandom(16)).decode("utf-8")
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
                        header in (HEADER_CONTENT_SECURITY_POLICY, HEADER_CONTENT_SECURITY_POLICY_REPORT_ONLY)
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
