import binascii
import re
import urllib
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response

from c2casgiutils.headers import ArmorHeaderMiddleware, _build_header


class State:
    """Simple state object for tests."""


@pytest.fixture
def mock_request():
    """Create a mock request with a simple state object."""
    request = MagicMock(spec=Request)
    request.base_url = urllib.parse.urlparse("http://example.com/")
    request.url = urllib.parse.urlparse("http://example.com/path")
    request.state = State()
    return request


def test_string_value():
    """Test with string input."""
    result = _build_header("text/html")
    assert result == "text/html"


def test_list_value_single_item():
    """Test with list containing single item."""
    result = _build_header(["'self'"])
    assert result == "'self'"


def test_list_value_multiple_items():
    """Test with list containing multiple items."""
    result = _build_header(["item1", "item2", "item3"])
    assert result == "item1; item2; item3"


def test_list_value_with_custom_separator():
    """Test with list and custom separator."""
    result = _build_header(["'self'", "https://example.com", "'unsafe-inline'"], separator=" ")
    assert result == "'self' https://example.com 'unsafe-inline'"


def test_list_value_with_final_separator():
    """Test with list and final separator."""
    result = _build_header(["item1", "item2", "item3"], final_separator=True)
    assert result == "item1; item2; item3; "


def test_list_value_empty():
    """Test with empty list."""
    result = _build_header([])
    assert result == ""


def test_list_value_empty_with_final_separator():
    """Test with empty list and final separator."""
    result = _build_header([], final_separator=True)
    assert result == ""


def test_dict_value_string_values():
    """Test with dict containing string values."""
    result = _build_header({"default-src": "'self'", "script-src": "'none'"})
    assert result == "default-src='self'; script-src='none'"


def test_dict_value_list_values():
    """Test with dict containing list values."""
    result = _build_header({"default-src": ["'self'"], "script-src": ["'self'", "https://example.com"]})
    assert result == "default-src='self'; script-src='self' https://example.com"


def test_dict_value_mixed_values():
    """Test with dict containing both string and list values."""
    result = _build_header({"max-age": "86400", "directives": ["includeSubDomains", "preload"]})
    assert result == "max-age=86400; directives=includeSubDomains preload"


def test_dict_value_with_custom_separators():
    """Test with dict and custom separators."""
    result = _build_header({"key1": "value1", "key2": "value2"}, separator=", ", dict_separator=": ")
    assert result == "key1: value1, key2: value2"


def test_dict_value_with_final_separator():
    """Test with dict and final separator."""
    result = _build_header({"default-src": "'self'", "script-src": "'none'"}, final_separator=True)
    assert result == "default-src='self'; script-src='none'; "


def test_dict_value_empty():
    """Test with empty dict."""
    result = _build_header({})
    assert result == ""


def test_dict_value_empty_with_final_separator():
    """Test with empty dict and final separator."""
    result = _build_header({}, final_separator=True)
    assert result == ""


def test_content_security_policy_format():
    """Test CSP-like formatting with space separator and final separator."""
    csp_dict = {
        "default-src": ["'self'"],
        "script-src": ["'self'", "https://cdnjs.cloudflare.com"],
        "style-src": ["'self'", "'unsafe-inline'"],
    }
    result = _build_header(csp_dict, dict_separator=" ", final_separator=True)
    expected = "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline'; "
    assert result == expected


def test_permissions_policy_format():
    """Test Permissions-Policy-like formatting with comma separator."""
    permissions = ["geolocation=()", "microphone=()"]
    result = _build_header(permissions, separator=", ")
    assert result == "geolocation=(), microphone=()"


def test_dict_with_invalid_value_type():
    """Test dict with unsupported value type raises TypeError."""
    with pytest.raises(
        TypeError,
        match=re.escape("Unsupported value type for header 'key': <class 'int'>. Expected str or list."),
    ):
        _build_header({"key": 123})


def test_dict_with_nested_dict_value():
    """Test dict with nested dict value raises TypeError."""
    with pytest.raises(
        TypeError,
        match=re.escape("Unsupported value type for header 'key': <class 'dict'>. Expected str or list."),
    ):
        _build_header({"key": {"nested": "value"}})


def test_unsupported_type_int():
    """Test with unsupported type raises TypeError."""
    with pytest.raises(
        TypeError,
        match=re.escape("Unsupported header type: <class 'int'>. Expected str, list, or dict."),
    ):
        _build_header(123)


def test_none_value():
    """Test with None input."""
    result = _build_header(None)
    assert result is None


def test_unsupported_type_tuple():
    """Test with tuple type raises TypeError."""
    with pytest.raises(
        TypeError,
        match=re.escape("Unsupported header type: <class 'tuple'>. Expected str, list, or dict."),
    ):
        _build_header(("item1", "item2"))


def test_real_world_strict_transport_security():
    """Test real-world Strict-Transport-Security header."""
    sts_list = [f"max-age={86400 * 30}", "includeSubDomains", "preload"]
    result = _build_header(sts_list)
    assert result == "max-age=2592000; includeSubDomains; preload"


def test_real_world_content_security_policy():
    """Test real-world Content-Security-Policy header."""
    csp = {
        "default-src": ["'self'"],
        "script-src": [
            "'self'",
            "https://cdnjs.cloudflare.com/ajax/libs/bootstrap/",
            "https://cdn.jsdelivr.net/npm/@sbrunner/",
        ],
        "style-src": ["'self'", "'unsafe-inline'", "https://cdnjs.cloudflare.com/ajax/libs/bootstrap/"],
    }
    result = _build_header(csp, dict_separator=" ", final_separator=True)
    expected = (
        "default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com/ajax/libs/bootstrap/ https://cdn.jsdelivr.net/npm/@sbrunner/; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com/ajax/libs/bootstrap/; "
    )
    assert result == expected


def test_init_default_config():
    """Test HeaderMiddleware initialization with default config."""
    app = Starlette()
    middleware = ArmorHeaderMiddleware(app)

    # Should have at least 2 configs (default and localhost)
    assert len(middleware.headers_config) >= 2

    # Check that headers are properly built
    default_config = next(
        (config for config in middleware.headers_config if config.netloc_match is None),
        None,
    )
    assert default_config is not None
    assert "Content-Security-Policy" in default_config.headers
    assert "X-Frame-Options" in default_config.headers


def test_init_custom_config():
    """Test HeaderMiddleware initialization with custom config."""
    app = Starlette()
    custom_config = {"test": {"headers": {"X-Custom-Header": "test-value"}}}
    middleware = ArmorHeaderMiddleware(app, custom_config)

    assert middleware.headers_config[-1].headers["X-Custom-Header"] == "test-value"


def test_init_with_regex_patterns():
    """Test HeaderMiddleware initialization with regex patterns."""
    app = Starlette()
    custom_config = {
        "api": {"netloc_match": r"^api\.", "path_match": r"^/v1/", "headers": {"X-API-Version": "1.0"}},
    }
    middleware = ArmorHeaderMiddleware(app, custom_config)

    config = middleware.headers_config[-1]
    assert config.netloc_match is not None
    assert config.path_match is not None
    assert config.netloc_match.pattern == r"^api\."
    assert config.path_match.pattern == r"^/v1/"


def test_init_with_status_code_filter():
    """Test HeaderMiddleware initialization with status code filter."""
    app = Starlette()
    custom_config = {"error": {"status_code": (400, 599), "headers": {"X-Error-Header": "error"}}}
    middleware = ArmorHeaderMiddleware(app, custom_config)

    config = middleware.headers_config[-1]
    assert config.status_code == (400, 599)


def test_init_header_processing_csp():
    """Test that CSP headers are processed with correct separators."""
    app = Starlette()
    custom_config = {
        "test": {
            "headers": {
                "Content-Security-Policy": {
                    "default-src": ["'self'"],
                    "script-src": ["'self'", "https://example.com"],
                },
            },
        },
    }
    middleware = ArmorHeaderMiddleware(app, custom_config)

    csp_header = middleware.headers_config[-1].headers["Content-Security-Policy"]
    assert csp_header.endswith("; ")  # Should have final separator
    csp_header_split = {e.strip() for e in csp_header.split("; ")}
    assert "default-src 'self'" in csp_header_split
    assert "script-src 'self' https://example.com" in csp_header_split


def test_init_header_processing_permissions_policy():
    """Test that Permissions-Policy headers are processed with comma separator."""
    app = Starlette()
    custom_config = {"test": {"headers": {"Permissions-Policy": ["geolocation=()", "microphone=()"]}}}
    middleware = ArmorHeaderMiddleware(app, custom_config)

    permissions_header = middleware.headers_config[0].headers["Permissions-Policy"]
    assert permissions_header == "geolocation=(), microphone=()"


@pytest.mark.asyncio
async def test_dispatch_basic_header_addition():
    """Test basic header addition in dispatch method."""

    # Create a simple ASGI app
    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    custom_config = {"test": {"headers": {"X-Test-Header": "test-value"}}}
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    # Create a mock request
    request = MagicMock(spec=Request)
    request.base_url = urllib.parse.urlparse("http://example.com/")
    request.url = urllib.parse.urlparse("http://example.com/path")

    # Create a mock call_next function
    mock_response = Response("Hello World")
    call_next = AsyncMock(return_value=mock_response)

    # Call dispatch
    result = await middleware.dispatch(request, call_next)

    # Check that header was added
    assert "X-Test-Header" in result.headers
    assert result.headers["X-Test-Header"] == "test-value"


@pytest.mark.asyncio
async def test_dispatch_netloc_matching():
    """Test netloc matching in dispatch method."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    custom_config = {
        "api": {"netloc_match": r"^api\.", "headers": {"X-API-Header": "api-value"}},
        "web": {"netloc_match": r"^www\.", "headers": {"X-Web-Header": "web-value"}},
    }
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    # Test API request
    request = MagicMock(spec=Request)
    request.base_url = urllib.parse.urlparse("http://api.example.com/")
    request.url = urllib.parse.urlparse("http://api.example.com/path")

    mock_response = Response("Hello World")
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(request, call_next)

    assert "X-API-Header" in result.headers
    assert "X-Web-Header" not in result.headers


@pytest.mark.asyncio
async def test_dispatch_path_matching():
    """Test path matching in dispatch method."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    custom_config = {"api": {"path_match": r"^api/", "headers": {"X-API-Path": "api-path"}}}
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    # Test API path
    request = MagicMock(spec=Request)
    request.base_url = urllib.parse.urlparse("http://example.com/")
    request.url = urllib.parse.urlparse("http://example.com/api/v1/users")

    mock_response = Response("Hello World")
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(request, call_next)

    assert "X-API-Path" in result.headers

    # Test non-API path
    request.url = urllib.parse.urlparse("http://example.com/static/css/style.css")
    del mock_response.headers["X-API-Path"]

    result = await middleware.dispatch(request, call_next)

    assert "X-API-Path" not in result.headers


@pytest.mark.asyncio
async def test_dispatch_status_code_matching_single():
    """Test status code matching with single value."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    custom_config = {"not_found": {"status_code": 404, "headers": {"X-Not-Found": "true"}}}
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    request = MagicMock(spec=Request)
    request.base_url = urllib.parse.urlparse("http://example.com/")
    request.url = urllib.parse.urlparse("http://example.com/path")

    # Test with 404 status
    mock_response = Response("Not Found", status_code=404)
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(request, call_next)
    assert "X-Not-Found" in result.headers

    # Test with 200 status
    mock_response = Response("OK", status_code=200)
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(request, call_next)
    assert "X-Not-Found" not in result.headers


@pytest.mark.asyncio
async def test_dispatch_status_code_matching_range():
    """Test status code matching with range."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    custom_config = {"client_error": {"status_code": (400, 499), "headers": {"X-Client-Error": "true"}}}
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    request = MagicMock(spec=Request)
    request.base_url = urllib.parse.urlparse("http://example.com/")
    request.url = urllib.parse.urlparse("http://example.com/path")

    # Test with 404 (in range)
    mock_response = Response("Not Found", status_code=404)
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(request, call_next)
    assert "X-Client-Error" in result.headers

    # Test with 500 (out of range)
    mock_response = Response("Server Error", status_code=500)
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(request, call_next)
    assert "X-Client-Error" not in result.headers


@pytest.mark.asyncio
async def test_dispatch_header_removal():
    """Test header removal when value is None."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    custom_config = {"remove": {"headers": {"X-Remove-Me": None, "X-Keep-Me": "keep-value"}}}
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    request = MagicMock(spec=Request)
    request.base_url = urllib.parse.urlparse("http://example.com/")
    request.url = urllib.parse.urlparse("http://example.com/path")

    # Create response with existing headers
    mock_response = Response("Hello World")
    mock_response.headers["X-Remove-Me"] = "remove-me"
    mock_response.headers["X-Existing"] = "existing"
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(request, call_next)

    assert "X-Remove-Me" not in result.headers
    assert "X-Keep-Me" in result.headers
    assert result.headers["X-Keep-Me"] == "keep-value"
    assert "X-Existing" in result.headers


@pytest.mark.asyncio
async def test_dispatch_multiple_configs_order():
    """Test that multiple configs are applied in order."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    custom_config = {
        "first": {"order": 1, "headers": {"X-Order": "first", "X-Shared": "first"}},
        "second": {"order": 2, "headers": {"X-Order": "second", "X-Shared": "second"}},
    }
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    request = MagicMock(spec=Request)
    request.base_url = urllib.parse.urlparse("http://example.com/")
    request.url = urllib.parse.urlparse("http://example.com/path")

    mock_response = Response("Hello World")
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(request, call_next)

    # Last config should win for shared headers
    assert result.headers["X-Shared"] == "second"


@pytest.mark.asyncio
async def test_dispatch_real_world_scenario():
    """Test a real-world scenario with CSP and security headers."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    # Use default config which includes CSP and security headers
    middleware = ArmorHeaderMiddleware(simple_app)

    request = MagicMock(spec=Request)
    request.base_url = urllib.parse.urlparse("http://example.com/")
    request.url = urllib.parse.urlparse("http://example.com/path")

    mock_response = Response("Hello World")
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(request, call_next)

    # Check that common security headers are present
    assert "Content-Security-Policy" in result.headers
    assert "X-Frame-Options" in result.headers
    assert "Strict-Transport-Security" in result.headers
    assert "X-Content-Type-Options" in result.headers

    # Check CSP format
    csp = result.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert csp.endswith("; ")


@pytest.mark.asyncio
async def test_dispatch_header_value_assignment_bug_fix():
    """Test that header values are correctly assigned (not header names)."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    custom_config = {"test": {"headers": {"X-Test-Header": "correct-value"}}}
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    request = MagicMock(spec=Request)
    request.base_url = urllib.parse.urlparse("http://example.com/")
    request.url = urllib.parse.urlparse("http://example.com/path")

    mock_response = Response("Hello World")
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(request, call_next)

    # This test would fail if the bug where header = header instead of header = value exists
    assert result.headers["X-Test-Header"] == "correct-value"
    assert result.headers["X-Test-Header"] != "X-Test-Header"


@pytest.mark.asyncio
async def test_dispatch_nonce_generation_and_replacement(mock_request):
    """Test that nonce is generated and replaced in CSP header."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    from c2casgiutils.headers import (
        CSP_DEFAULT_SRC,
        CSP_NONCE,
        CSP_SCRIPT_SRC,
        CSP_SELF,
        HEADER_CONTENT_SECURITY_POLICY,
    )

    custom_config = {
        "test": {
            "headers": {
                HEADER_CONTENT_SECURITY_POLICY: {
                    CSP_DEFAULT_SRC: [CSP_SELF],
                    CSP_SCRIPT_SRC: [CSP_SELF, CSP_NONCE],
                },
            },
        },
    }
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    mock_response = Response("Hello World")
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(mock_request, call_next)

    # Check that nonce was generated and set on request.state
    assert hasattr(mock_request.state, "nonce")
    nonce = mock_request.state.nonce
    assert nonce is not None
    assert len(nonce) > 0

    # Check that CSP header contains the nonce
    csp = result.headers[HEADER_CONTENT_SECURITY_POLICY]
    assert f"'nonce-{nonce}'" in csp
    assert CSP_NONCE not in csp  # Placeholder should be replaced


@pytest.mark.asyncio
async def test_dispatch_nonce_replacement_in_csp_report_only(mock_request):
    """Test that nonce is replaced in Content-Security-Policy-Report-Only header."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    from c2casgiutils.headers import (
        CSP_DEFAULT_SRC,
        CSP_NONCE,
        CSP_SCRIPT_SRC,
        CSP_SELF,
        HEADER_CONTENT_SECURITY_POLICY_REPORT_ONLY,
    )

    custom_config = {
        "test": {
            "headers": {
                HEADER_CONTENT_SECURITY_POLICY_REPORT_ONLY: {
                    CSP_DEFAULT_SRC: [CSP_SELF],
                    CSP_SCRIPT_SRC: [CSP_SELF, CSP_NONCE],
                },
            },
        },
    }
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    mock_response = Response("Hello World")
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(mock_request, call_next)

    # Check that nonce was generated
    assert hasattr(mock_request.state, "nonce")
    nonce = mock_request.state.nonce

    # Check that CSP-Report-Only header contains the nonce
    csp = result.headers[HEADER_CONTENT_SECURITY_POLICY_REPORT_ONLY]
    assert f"'nonce-{nonce}'" in csp
    assert CSP_NONCE not in csp


@pytest.mark.asyncio
async def test_dispatch_nonce_multiple_placeholders(mock_request):
    """Test that multiple nonce placeholders are replaced correctly."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    from c2casgiutils.headers import (
        CSP_DEFAULT_SRC,
        CSP_NONCE,
        CSP_SCRIPT_SRC,
        CSP_SELF,
        CSP_STYLE_SRC,
        HEADER_CONTENT_SECURITY_POLICY,
    )

    custom_config = {
        "test": {
            "headers": {
                HEADER_CONTENT_SECURITY_POLICY: {
                    CSP_DEFAULT_SRC: [CSP_SELF],
                    CSP_SCRIPT_SRC: [CSP_SELF, CSP_NONCE],
                    CSP_STYLE_SRC: [CSP_SELF, CSP_NONCE],
                },
            },
        },
    }
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    mock_response = Response("Hello World")
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(mock_request, call_next)

    # Check that nonce was generated
    nonce = mock_request.state.nonce

    # Check that all nonce placeholders are replaced
    csp = result.headers[HEADER_CONTENT_SECURITY_POLICY]
    assert csp.count(f"'nonce-{nonce}'") == 2  # Should appear twice
    assert CSP_NONCE not in csp  # Placeholder should not remain


@pytest.mark.asyncio
async def test_dispatch_nonce_not_generated_when_not_needed(mock_request):
    """Test that nonce is not generated when CSP doesn't include nonce placeholder."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    from c2casgiutils.headers import (
        CSP_DEFAULT_SRC,
        CSP_SCRIPT_SRC,
        CSP_SELF,
        HEADER_CONTENT_SECURITY_POLICY,
    )

    custom_config = {
        "test": {
            "headers": {
                HEADER_CONTENT_SECURITY_POLICY: {
                    CSP_DEFAULT_SRC: [CSP_SELF],
                    CSP_SCRIPT_SRC: [CSP_SELF],
                },
            },
        },
    }
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    mock_response = Response("Hello World")
    call_next = AsyncMock(return_value=mock_response)

    await middleware.dispatch(mock_request, call_next)

    # Check that nonce was not generated
    assert not hasattr(mock_request.state, "nonce")


@pytest.mark.asyncio
async def test_dispatch_nonce_uniqueness():
    """Test that each request gets a unique nonce."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    from c2casgiutils.headers import (
        CSP_DEFAULT_SRC,
        CSP_NONCE,
        CSP_SCRIPT_SRC,
        CSP_SELF,
        HEADER_CONTENT_SECURITY_POLICY,
    )

    custom_config = {
        "test": {
            "headers": {
                HEADER_CONTENT_SECURITY_POLICY: {
                    CSP_DEFAULT_SRC: [CSP_SELF],
                    CSP_SCRIPT_SRC: [CSP_SELF, CSP_NONCE],
                },
            },
        },
    }
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    nonces = []
    for _ in range(5):
        request = MagicMock(spec=Request)
        request.base_url = urllib.parse.urlparse("http://example.com/")
        request.url = urllib.parse.urlparse("http://example.com/path")
        request.state = State()

        mock_response = Response("Hello World")
        call_next = AsyncMock(return_value=mock_response)

        await middleware.dispatch(request, call_next)
        nonces.append(request.state.nonce)

    # Check that all nonces are unique
    assert len(nonces) == len(set(nonces))


@pytest.mark.asyncio
async def test_dispatch_nonce_with_multiple_configs(mock_request):
    """Test nonce generation stops after first match but both configs are applied."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    from c2casgiutils.headers import (
        CSP_DEFAULT_SRC,
        CSP_NONCE,
        CSP_SCRIPT_SRC,
        CSP_SELF,
        HEADER_CONTENT_SECURITY_POLICY,
        HEADER_X_CONTENT_TYPE_OPTIONS,
    )

    custom_config = {
        "first": {
            "order": 1,
            "headers": {
                HEADER_CONTENT_SECURITY_POLICY: {
                    CSP_DEFAULT_SRC: [CSP_SELF],
                    CSP_SCRIPT_SRC: [CSP_SELF, CSP_NONCE],
                },
            },
        },
        "second": {
            "order": 2,
            "headers": {
                HEADER_CONTENT_SECURITY_POLICY: {
                    CSP_DEFAULT_SRC: [CSP_SELF],
                    CSP_SCRIPT_SRC: [CSP_SELF, CSP_NONCE],
                },
                HEADER_X_CONTENT_TYPE_OPTIONS: "nosniff",
            },
        },
    }
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    mock_response = Response("Hello World")
    call_next = AsyncMock(return_value=mock_response)

    result = await middleware.dispatch(mock_request, call_next)

    # Should only generate one nonce
    nonce = mock_request.state.nonce
    assert nonce is not None

    # Both headers should use the same nonce
    csp = result.headers[HEADER_CONTENT_SECURITY_POLICY]
    assert f"'nonce-{nonce}'" in csp

    # Verify second config was also applied
    assert result.headers[HEADER_X_CONTENT_TYPE_OPTIONS] == "nosniff"


@pytest.mark.asyncio
async def test_dispatch_nonce_base64_encoding(mock_request):
    """Test that nonce is properly base64 encoded."""

    async def simple_app(scope, receive, send):
        response = Response("Hello World")
        await response(scope, receive, send)

    import base64

    from c2casgiutils.headers import (
        CSP_DEFAULT_SRC,
        CSP_NONCE,
        CSP_SCRIPT_SRC,
        CSP_SELF,
        HEADER_CONTENT_SECURITY_POLICY,
    )

    custom_config = {
        "test": {
            "headers": {
                HEADER_CONTENT_SECURITY_POLICY: {
                    CSP_DEFAULT_SRC: [CSP_SELF],
                    CSP_SCRIPT_SRC: [CSP_SELF, CSP_NONCE],
                },
            },
        },
    }
    middleware = ArmorHeaderMiddleware(simple_app, custom_config)

    mock_response = Response("Hello World")
    call_next = AsyncMock(return_value=mock_response)

    await middleware.dispatch(mock_request, call_next)

    nonce = mock_request.state.nonce

    # Verify it's valid base64
    try:
        base64.b64decode(nonce)
        valid_base64 = True
    except (ValueError, binascii.Error):
        valid_base64 = False

    assert valid_base64, "Nonce should be valid base64"
