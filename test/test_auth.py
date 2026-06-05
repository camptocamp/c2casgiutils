from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from fastapi import Response
from starlette.requests import Request

from c2casgiutils import auth


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
async def test_check_access_config_refreshes_expired_token(fixed_cookie_path):
    auth_info = auth.AuthInfo(
        is_logged_in=True,
        user=auth.UserInfo(login="john", token="old-token"),
        session_payload={
            "login": "john",
            "display_name": "John",
            "url": "https://example.com/john",
            "token": "old-token",
            "access_token_expires_at": auth._now_utc_timestamp() - 1,
            "refresh_token": "refresh-token",
            "refresh_token_expires_at": auth._now_utc_timestamp() + 3600,
        },
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

        has_access = await auth.check_access_config(
            auth_info,
            auth.AuthConfig(github_repository="camptocamp/tilecloud-chain", github_access_type="pull"),
            request=request,
            fastapi_response=response,
        )

    assert has_access is True
    assert auth_info.user.token == "new-token"
    assert auth_info.is_logged_in is True
    assert auth_info.session_payload is not None
    assert auth_info.session_payload["token"] == "new-token"
    assert "access_token_expires_at" in auth_info.session_payload
    mock_set_cookie.assert_called_once()


@pytest.mark.asyncio
async def test_check_access_config_logs_out_when_refresh_fails(fixed_cookie_path):
    auth_info = auth.AuthInfo(
        is_logged_in=True,
        user=auth.UserInfo(login="john", token="expired-token"),
        session_payload={
            "login": "john",
            "display_name": "John",
            "url": "https://example.com/john",
            "token": "expired-token",
            "access_token_expires_at": auth._now_utc_timestamp() - 1,
            "refresh_token": "refresh-token",
            "refresh_token_expires_at": auth._now_utc_timestamp() + 3600,
        },
    )

    with patch("c2casgiutils.auth._refresh_github_access_token", new=AsyncMock(return_value=None)):
        has_access = await auth.check_access_config(
            auth_info,
            auth.AuthConfig(github_repository="camptocamp/tilecloud-chain", github_access_type="pull"),
            request=_request(),
            fastapi_response=Response(),
        )

    assert has_access is False
    assert auth_info.is_logged_in is False
    assert auth_info.user.token == ""
    assert auth_info.session_payload is None


@pytest.mark.asyncio
async def test_check_access_config_logs_out_when_no_refresh_token(fixed_cookie_path):
    auth_info = auth.AuthInfo(
        is_logged_in=True,
        user=auth.UserInfo(login="john", token="expired-token"),
        session_payload={
            "login": "john",
            "display_name": "John",
            "url": "https://example.com/john",
            "token": "expired-token",
            "access_token_expires_at": auth._now_utc_timestamp() - 1,
        },
    )

    has_access = await auth.check_access_config(
        auth_info,
        auth.AuthConfig(github_repository="camptocamp/tilecloud-chain", github_access_type="pull"),
        request=_request(),
        fastapi_response=Response(),
    )

    assert has_access is False
    assert auth_info.is_logged_in is False
    assert auth_info.user.token == ""
    assert auth_info.session_payload is None


@pytest.mark.asyncio
async def test_check_access_config_denies_without_logout_when_missing_permission(fixed_cookie_path):
    auth_info = auth.AuthInfo(
        is_logged_in=True,
        user=auth.UserInfo(login="john", token="valid-token"),
        session_payload={
            "login": "john",
            "display_name": "John",
            "url": "https://example.com/john",
            "token": "valid-token",
            "access_token_expires_at": auth._now_utc_timestamp() + 3600,
        },
    )

    github_response = _mock_github_get_response(200, {"permissions": {"pull": False}})
    with patch("c2casgiutils.auth.aiohttp.ClientSession") as mock_client_session:
        _setup_client_session_get(mock_client_session, github_response)

        has_access = await auth.check_access_config(
            auth_info,
            auth.AuthConfig(github_repository="camptocamp/tilecloud-chain", github_access_type="pull"),
            request=_request(),
            fastapi_response=Response(),
        )

    assert has_access is False
    assert auth_info.is_logged_in is True
    assert auth_info.user.token == "valid-token"


def test_apply_token_lifetimes_clears_stale_refresh_expiration():
    payload = {
        "refresh_token": "old-refresh",
        "refresh_token_expires_at": auth._now_utc_timestamp() + 10,
    }

    auth._apply_token_lifetimes(
        payload,
        {
            "access_token": "new-token",
            "token_type": "bearer",
            "refresh_token": "new-refresh",
        },
    )

    assert payload["refresh_token"] == "new-refresh"
    assert "refresh_token_expires_at" not in payload


@pytest.mark.asyncio
async def test_refresh_github_access_token_handles_network_error():
    with patch("c2casgiutils.auth.aiohttp.ClientSession", side_effect=aiohttp.ClientError("boom")):
        token = await auth._refresh_github_access_token("refresh-token")

    assert token is None
