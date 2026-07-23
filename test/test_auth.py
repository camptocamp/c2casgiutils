from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from fastapi import Response
from starlette.requests import Request

from c2casgiutils import auth
from c2casgiutils.config import GitHubAccessType


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
        }
    )


def _request_with_auth_header(token: str) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
        }
    )


@pytest.fixture
def fixed_cookie_path() -> str:
    previous = auth.settings.auth.jwt.cookie.path
    auth.settings.auth.jwt.cookie.path = "/"
    yield "/"
    auth.settings.auth.jwt.cookie.path = previous


def _mock_github_get_response(status: int, payload: dict) -> Mock:
    github_response = Mock()
    github_response.status = status
    github_response.json = AsyncMock(return_value=payload)
    return github_response


def _setup_client_session_get(mock_client_session: Mock, github_response: Mock) -> None:
    session = Mock()
    get_cm = AsyncMock()
    get_cm.__aenter__.return_value = github_response
    get_cm.__aexit__.return_value = None
    session.get.return_value = get_cm

    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = session
    session_cm.__aexit__.return_value = None
    mock_client_session.return_value = session_cm


@pytest.mark.asyncio
async def test_ensure_valid_github_token_refreshes_expired_token(fixed_cookie_path):
    auth_info = auth.AuthInfo(
        is_logged_in=True,
        user=auth.UserInfo(login="john", token="old-token"),
        session_payload=auth.GitHubSessionPayload(
            login="john",
            display_name="John",
            url="https://example.com/john",
            token="old-token",
            access_token_expires_at=auth._now_utc_timestamp() - 1,
            refresh_token="refresh-token",
            refresh_token_expires_at=auth._now_utc_timestamp() + 3600,
        ),
    )
    request = _request()
    response = Response()

    refreshed_token = {
        "access_token": "new-token",
        "token_type": "bearer",
        "expires_in": 3600,
        "refresh_token": "new-refresh-token",
        "refresh_token_expires_in": 7200,
    }

    github_response = _mock_github_get_response(200, {"permissions": {"pull": True}})

    with (
        patch("c2casgiutils.auth._refresh_github_access_token", new=AsyncMock(return_value=refreshed_token)),
        patch("c2casgiutils.auth._set_jwt_cookie") as mock_set_cookie,
        patch("c2casgiutils.auth.aiohttp.ClientSession") as mock_client_session,
    ):
        _setup_client_session_get(mock_client_session, github_response)

        has_access = await auth._ensure_valid_github_token(request, response, auth_info)

    assert has_access is True
    assert auth_info.user.token == "new-token"
    assert auth_info.is_logged_in is True
    assert auth_info.session_payload is not None
    assert auth_info.session_payload.token == "new-token"
    assert auth_info.session_payload.access_token_expires_at is not None
    mock_set_cookie.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_valid_github_token_logs_out_when_refresh_fails(fixed_cookie_path):
    auth_info = auth.AuthInfo(
        is_logged_in=True,
        user=auth.UserInfo(login="john", token="expired-token"),
        session_payload=auth.GitHubSessionPayload(
            login="john",
            display_name="John",
            url="https://example.com/john",
            token="expired-token",
            access_token_expires_at=auth._now_utc_timestamp() - 1,
            refresh_token="refresh-token",
            refresh_token_expires_at=auth._now_utc_timestamp() + 3600,
        ),
    )

    with patch("c2casgiutils.auth._refresh_github_access_token", new=AsyncMock(return_value=None)):
        has_access = await auth._ensure_valid_github_token(_request(), Response(), auth_info)

    assert has_access is False
    assert auth_info.is_logged_in is False
    assert auth_info.user.token == ""
    assert auth_info.session_payload is None


@pytest.mark.asyncio
async def test_ensure_valid_github_token_logs_out_when_no_refresh_token(fixed_cookie_path):
    auth_info = auth.AuthInfo(
        is_logged_in=True,
        user=auth.UserInfo(login="john", token="expired-token"),
        session_payload=auth.GitHubSessionPayload(
            login="john",
            display_name="John",
            url="https://example.com/john",
            token="expired-token",
            access_token_expires_at=auth._now_utc_timestamp() - 1,
        ),
    )

    has_access = await auth._ensure_valid_github_token(_request(), Response(), auth_info)

    assert has_access is False
    assert auth_info.is_logged_in is False
    assert auth_info.user.token == ""
    assert auth_info.session_payload is None


@pytest.mark.asyncio
async def test_check_access_config_denies_without_logout_when_missing_permission(fixed_cookie_path):
    auth_info = auth.AuthInfo(
        is_logged_in=True,
        user=auth.UserInfo(login="john", token="valid-token"),
        session_payload=auth.GitHubSessionPayload(
            login="john",
            display_name="John",
            url="https://example.com/john",
            token="valid-token",
            access_token_expires_at=auth._now_utc_timestamp() + 3600,
        ),
    )

    github_response = _mock_github_get_response(200, {"permissions": {"pull": False}})
    with patch("c2casgiutils.auth.aiohttp.ClientSession") as mock_client_session:
        _setup_client_session_get(mock_client_session, github_response)

        has_access = await auth.check_access_config(
            auth_info,
            auth.AuthConfig(
                github_repository="camptocamp/tilecloud-chain",
                github_access_type_read_only=GitHubAccessType.PULL,
            ),
            request=_request(),
            fastapi_response=Response(),
        )

    assert has_access is False
    assert auth_info.is_logged_in is True
    assert auth_info.user.token == "valid-token"


@pytest.mark.asyncio
async def test_check_access_config_does_not_refresh_token(fixed_cookie_path):
    auth_info = auth.AuthInfo(
        is_logged_in=True,
        user=auth.UserInfo(login="john", token="expired-token"),
        session_payload=auth.GitHubSessionPayload(
            login="john",
            display_name="John",
            url="https://example.com/john",
            token="expired-token",
            access_token_expires_at=auth._now_utc_timestamp() - 1,
            refresh_token="refresh-token",
            refresh_token_expires_at=auth._now_utc_timestamp() + 3600,
        ),
    )

    github_response = _mock_github_get_response(200, {"permissions": {"pull": True}})

    with (
        patch(
            "c2casgiutils.auth._ensure_valid_github_token", new=AsyncMock(return_value=False)
        ) as mock_ensure,
        patch("c2casgiutils.auth.aiohttp.ClientSession") as mock_client_session,
    ):
        _setup_client_session_get(mock_client_session, github_response)

        has_access = await auth.check_access_config(
            auth_info,
            auth.AuthConfig(
                github_repository="camptocamp/tilecloud-chain",
                github_access_type_read_only=GitHubAccessType.PULL,
            ),
            request=_request(),
            fastapi_response=Response(),
        )

    assert has_access is True
    assert auth_info.is_logged_in is True
    assert auth_info.user.token == "expired-token"
    mock_ensure.assert_not_called()


def test_apply_token_lifetimes_clears_stale_refresh_expiration():
    payload = auth.GitHubSessionPayload(
        refresh_token="old-refresh", refresh_token_expires_at=auth._now_utc_timestamp() + 10
    )

    auth._apply_token_lifetimes(
        payload,
        {
            "access_token": "new-token",
            "token_type": "bearer",
            "refresh_token": "new-refresh",
        },
    )

    assert payload.refresh_token == "new-refresh"
    assert payload.refresh_token_expires_at is None


@pytest.mark.asyncio
async def test_refresh_github_access_token_handles_network_error():
    with patch("c2casgiutils.auth.aiohttp.ClientSession", side_effect=aiohttp.ClientError("boom")):
        token = await auth._refresh_github_access_token("refresh-token")

    assert token is None


@pytest.mark.asyncio
async def test_access_context_require_access_raises_forbidden():
    access_context = auth.AccessContext(
        auth_info=auth.AuthInfo(is_logged_in=False, user=auth.UserInfo()),
        request=_request(),
        response=Response(),
    )

    with pytest.raises(auth.HTTPException) as exception:
        await access_context.require_access(
            auth.AuthConfig(
                github_repository="camptocamp/tilecloud-chain",
                github_access_type_read_only=GitHubAccessType.PULL,
            )
        )

    assert exception.value.status_code == 403


@pytest.mark.asyncio
async def test_is_auth_user_github_clears_cookie_on_expired_jwt(fixed_cookie_path):
    response = Response()

    with (
        patch("c2casgiutils.auth._get_jwt_cookie", side_effect=auth.jwt.ExpiredSignatureError("expired")),
        pytest.raises(auth.HTTPException) as exception,
    ):
        await auth._is_auth_user_github(_request(), response)

    assert exception.value.status_code == 401
    assert "set-cookie" in response.headers
    assert f"{auth.settings.auth.jwt.cookie.name}=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_is_auth_user_github_clears_cookie_on_invalid_jwt(fixed_cookie_path):
    response = Response()

    with (
        patch("c2casgiutils.auth._get_jwt_cookie", side_effect=auth.jwt.InvalidTokenError("invalid")),
        pytest.raises(auth.HTTPException) as exception,
    ):
        await auth._is_auth_user_github(_request(), response)

    assert exception.value.status_code == 401
    assert "set-cookie" in response.headers
    assert f"{auth.settings.auth.jwt.cookie.name}=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_validate_github_token_success():
    token = "valid-token"
    user_response = Mock()
    user_response.status = 200
    user_response.json = AsyncMock(return_value={"login": "testuser", "name": "Test User"})

    session = Mock()
    get_cm = AsyncMock()
    get_cm.__aenter__.return_value = user_response
    get_cm.__aexit__.return_value = None
    session.get.return_value = get_cm

    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = session
    session_cm.__aexit__.return_value = None

    with patch("c2casgiutils.auth.aiohttp.ClientSession", return_value=session_cm):
        login, name = await auth._validate_github_token(token)

    assert login == "testuser"
    assert name == "Test User"
    session.get.assert_called_once_with(
        "https://api.github.com/user",
        headers={
            "Authorization": "Bearer valid-token",
            "Accept": "application/json",
        },
    )


@pytest.mark.asyncio
async def test_validate_github_token_invalid():
    token = "invalid-token"
    user_response = Mock()
    user_response.status = 401

    session = Mock()
    get_cm = AsyncMock()
    get_cm.__aenter__.return_value = user_response
    get_cm.__aexit__.return_value = None
    session.get.return_value = get_cm

    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = session
    session_cm.__aexit__.return_value = None

    with patch("c2casgiutils.auth.aiohttp.ClientSession", return_value=session_cm):
        login, name = await auth._validate_github_token(token)

    assert login is None
    assert name is None


@pytest.mark.asyncio
async def test_validate_github_token_network_error():
    with patch("c2casgiutils.auth.aiohttp.ClientSession", side_effect=aiohttp.ClientError("boom")):
        login, name = await auth._validate_github_token("token")

    assert login is None
    assert name is None


@pytest.mark.asyncio
async def test_get_auth_with_bearer_token_success():
    with patch(
        "c2casgiutils.auth._validate_github_token", new=AsyncMock(return_value=("testuser", "Test User"))
    ):
        request = _request_with_auth_header("valid-token")
        response = Response()
        auth_info = await auth.get_auth(request, response)

    assert auth_info.is_logged_in is True
    assert auth_info.user.login == "testuser"
    assert auth_info.user.display_name == "Test User"
    assert auth_info.user.url == "https://github.com/testuser"
    assert auth_info.user.token == "valid-token"


@pytest.mark.asyncio
async def test_get_auth_with_bearer_token_invalid():
    with patch("c2casgiutils.auth._validate_github_token", new=AsyncMock(return_value=(None, None))):
        request = _request_with_auth_header("invalid-token")
        response = Response()
        auth_info = await auth.get_auth(request, response)

    assert auth_info.is_logged_in is False


@pytest.mark.asyncio
async def test_get_auth_with_bearer_token_no_github_config():
    with patch(
        "c2casgiutils.auth._validate_github_token", new=AsyncMock(return_value=("testuser", "Test User"))
    ):
        request = _request_with_auth_header("valid-token")
        response = Response()
        auth_info = await auth.get_auth(request, response)

    assert auth_info.is_logged_in is True
    assert auth_info.user.login == "testuser"


@pytest.mark.asyncio
async def test_check_read_only_access_returns_true_when_not_github_auth():
    auth_info = auth.AuthInfo(
        is_logged_in=True,
        user=auth.UserInfo(login="test", token="token"),
    )

    has_access = await auth.check_read_only_access(auth_info)

    assert has_access is True


@pytest.mark.asyncio
async def test_check_read_only_access_returns_false_when_not_logged_in():
    auth_info = auth.AuthInfo(
        is_logged_in=False,
        user=auth.UserInfo(),
    )

    has_access = await auth.check_read_only_access(auth_info)

    assert has_access is False


@pytest.mark.asyncio
async def test_check_read_write_access_returns_true_when_not_github_auth():
    auth_info = auth.AuthInfo(
        is_logged_in=True,
        user=auth.UserInfo(login="test", token="token"),
    )

    has_access = await auth.check_read_write_access(auth_info)

    assert has_access is True


@pytest.mark.asyncio
async def test_check_read_write_access_returns_false_when_not_logged_in():
    auth_info = auth.AuthInfo(
        is_logged_in=False,
        user=auth.UserInfo(),
    )

    has_access = await auth.check_read_write_access(auth_info)

    assert has_access is False


@pytest.mark.asyncio
async def test_access_context_require_read_only_access_raises_forbidden():
    access_context = auth.AccessContext(
        auth_info=auth.AuthInfo(is_logged_in=False, user=auth.UserInfo()),
        request=_request(),
        response=Response(),
    )

    with pytest.raises(auth.HTTPException) as exception:
        await access_context.require_read_only_access()

    assert exception.value.status_code == 403


@pytest.mark.asyncio
async def test_access_context_require_read_write_access_raises_forbidden():
    access_context = auth.AccessContext(
        auth_info=auth.AuthInfo(is_logged_in=False, user=auth.UserInfo()),
        request=_request(),
        response=Response(),
    )

    with pytest.raises(auth.HTTPException) as exception:
        await access_context.require_read_write_access()

    assert exception.value.status_code == 403
