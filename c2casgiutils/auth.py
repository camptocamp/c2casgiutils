import datetime
import logging
import secrets
import urllib.parse
from enum import Enum
from typing import Annotated, Any, Literal, cast

import aiohttp
import jwt
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyHeader, APIKeyQuery
from pydantic import BaseModel, Field, ValidationError

from c2casgiutils.config import settings

_LOG = logging.getLogger(__name__)

# Security schemes
api_key_query = APIKeyQuery(name="secret", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthConfig(BaseModel):
    """Configuration of the authentication."""

    # The repository to check access to (<organization>/<repository>).
    github_repository: str | None = None
    # The type of access to check (admin|push|pull).
    github_access_type: str | None = None


ADMIN_AUTH_CONFIG = AuthConfig(
    github_repository=settings.auth.github.repository,
    github_access_type="admin",
)


class UserInfo(BaseModel):
    """Details about the user authenticated with GitHub."""

    login: str = ""
    display_name: str = ""
    url: str = ""
    token: str = ""


class GitHubSessionPayload(UserInfo):
    """Typed payload stored in the GitHub auth session cookie."""

    access_token_expires_at: int | None = None
    refresh_token: str | None = None
    refresh_token_expires_at: int | None = None


class AuthInfo(BaseModel):
    """Details about the authentication status and user information."""

    is_logged_in: bool
    user: UserInfo
    session_payload: GitHubSessionPayload | None = Field(default=None, exclude=True)


class AccessContext:
    """Request-scoped authentication context for access checks."""

    def __init__(self, auth_info: AuthInfo, request: Request, response: Response) -> None:
        self.auth_info = auth_info
        self.request = request
        self.response = response

    async def check_access(self, auth_config: AuthConfig) -> bool:
        """Check whether the current user has access to the configured repository."""
        return await check_access(self.auth_info, auth_config, request=self.request, response=self.response)

    async def check_admin_access(self) -> bool:
        """Check whether the current user has admin access."""
        return await check_admin_access(self.auth_info, request=self.request, response=self.response)

    async def require_access(self, auth_config: AuthConfig) -> None:
        """Require access to the configured repository or raise HTTP 403."""
        if not await self.check_access(auth_config):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this resource",
            )

    async def require_admin_access(self) -> None:
        """Require admin access or raise HTTP 403."""
        if not await self.check_admin_access():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have admin access to this resource",
            )


async def _is_auth_secret(
    request: Request,
    response: Response,
    query_secret: Annotated[str | None, Depends(api_key_query)] = None,
    header_secret: Annotated[str | None, Depends(api_key_header)] = None,
) -> bool:
    if not settings.auth.secret:
        return False

    expected = settings.auth.secret
    secret = query_secret or header_secret
    if secret is None:
        try:
            secret_payload = _get_jwt_cookie(request)
            if secret_payload is not None:
                secret = secret_payload.get("secret")
        except jwt.ExpiredSignatureError:
            _LOG.warning("Expired JWT cookie")
        except jwt.InvalidTokenError as jwt_exception:
            _LOG.warning("Invalid JWT cookie", exc_info=jwt_exception)

    if secret is not None:
        if secret == "":  # nosec
            # Logout
            response.delete_cookie(key=settings.auth.jwt.cookie.name, path=_get_jwt_cookie_path(request))
            return False
        if secret != expected:
            return False
        # Login or refresh the cookie
        _set_jwt_cookie(
            request,
            response,
            payload={
                "secret": secret,
            },
        )
        # Since this could be used from outside c2cwsgiutils views, we cannot set the path to c2c
        return True
    return False


def _logout_user(request: Request, response: Response, auth_info: AuthInfo) -> None:
    """Clear authentication cookie and reset auth information."""
    response.delete_cookie(key=settings.auth.jwt.cookie.name, path=_get_jwt_cookie_path(request))
    auth_info.is_logged_in = False
    auth_info.user = UserInfo()
    auth_info.session_payload = None


def _now_utc_timestamp() -> int:
    """Get the current UTC timestamp in seconds."""
    return int(datetime.datetime.now(datetime.UTC).timestamp())


def _is_expired(expiration_timestamp: float | None) -> bool:
    """Check if a token expiration timestamp is considered expired with margin."""
    if expiration_timestamp is None:
        return False
    return _now_utc_timestamp() + int(
        settings.auth.github.access_token_expiration_margin.total_seconds()
    ) >= int(expiration_timestamp)


def _apply_token_lifetimes(payload: GitHubSessionPayload, token: dict[str, Any]) -> None:
    """Apply token expiration fields from an OAuth response payload."""
    now = _now_utc_timestamp()

    expires_in = token.get("expires_in")
    if isinstance(expires_in, int | float):
        payload.access_token_expires_at = now + int(expires_in)
    else:
        payload.access_token_expires_at = None

    refresh_token = token.get("refresh_token")
    if isinstance(refresh_token, str) and refresh_token:
        payload.refresh_token = refresh_token

    refresh_token_expires_in = token.get("refresh_token_expires_in")
    if isinstance(refresh_token_expires_in, int | float):
        payload.refresh_token_expires_at = now + int(refresh_token_expires_in)
    elif isinstance(refresh_token, str) and refresh_token:
        payload.refresh_token_expires_at = None


async def _refresh_github_access_token(refresh_token: str) -> dict[str, Any] | None:
    """Try to refresh a GitHub access token."""
    token_url = settings.auth.github.token_url
    token_data = {
        "client_id": settings.auth.github.client_id,
        "client_secret": settings.auth.github.client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    headers = {"Accept": "application/json"}

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                token_url,
                data=token_data,
                headers=headers,
            ) as response_token,
        ):
            if response_token.status != 200:
                _LOG.info("Unable to refresh GitHub token: %s", await response_token.text())
                return None
            token_raw = await response_token.json()
            if not isinstance(token_raw, dict):
                _LOG.warning("Invalid refreshed token payload: expected object")
                return None
            token = cast("dict[str, Any]", token_raw)
    except (aiohttp.ClientError, TimeoutError, ValueError) as exception:
        _LOG.warning("Unable to refresh GitHub token", exc_info=exception)
        return None

    token_type = token.get("token_type")
    if token_type is None or token_type.lower() != "bearer":
        _LOG.warning("Invalid refreshed token type: %r", token_type)
        return None
    if not isinstance(token.get("access_token"), str) or not token["access_token"]:
        _LOG.warning("Invalid refreshed token payload: missing access_token")
        return None
    return token


async def _ensure_valid_github_token(
    request: Request,
    response: Response,
    auth_info: AuthInfo,
) -> bool:
    """Ensure a valid GitHub token is available, refresh or logout if needed."""
    if not auth_info.is_logged_in:
        return False

    payload = auth_info.session_payload
    if payload is None:
        return False

    if not _is_expired(payload.access_token_expires_at):
        return True

    refresh_token = payload.refresh_token
    if not refresh_token:
        _logout_user(request, response, auth_info)
        return False
    if _is_expired(payload.refresh_token_expires_at):
        _logout_user(request, response, auth_info)
        return False

    token = await _refresh_github_access_token(refresh_token)
    if token is None:
        _logout_user(request, response, auth_info)
        return False

    payload.token = token["access_token"]
    _apply_token_lifetimes(payload, token)
    _set_jwt_cookie(request, response, payload=payload.model_dump(exclude_none=True))
    auth_info.user.token = token["access_token"]
    auth_info.session_payload = payload
    return True


async def _is_auth_user_github(request: Request, response: Response) -> AuthInfo:
    if settings.auth.test.username is not None:
        # For testing purposes, we can return a fake user
        return AuthInfo(
            is_logged_in=True,
            user=UserInfo(
                login="test",
                display_name=settings.auth.test.username,
                url="https://example.com",
                token="",  # nosec
            ),
        )
    try:
        user_payload = _get_jwt_cookie(request)
    except jwt.ExpiredSignatureError as jwt_exception:
        response.delete_cookie(key=settings.auth.jwt.cookie.name, path=_get_jwt_cookie_path(request))
        raise HTTPException(401, "Expired session") from jwt_exception
    except jwt.InvalidTokenError as jwt_exception:
        response.delete_cookie(key=settings.auth.jwt.cookie.name, path=_get_jwt_cookie_path(request))
        raise HTTPException(401, "Invalid session") from jwt_exception

    session_payload: GitHubSessionPayload | None = None
    if user_payload is not None:
        try:
            session_payload = GitHubSessionPayload.model_validate(user_payload)
        except ValidationError as validation_exception:
            response.delete_cookie(key=settings.auth.jwt.cookie.name, path=_get_jwt_cookie_path(request))
            raise HTTPException(401, "Invalid session") from validation_exception

    auth_info = AuthInfo(
        is_logged_in=user_payload is not None,
        user=UserInfo(**(user_payload or {})),
        session_payload=session_payload,
    )

    if not auth_info.is_logged_in:
        return auth_info

    await _ensure_valid_github_token(request, response, auth_info)
    return auth_info


async def get_auth(request: Request, response: Response) -> AuthInfo:
    """
    Check if the client is authenticated.

    Returns: boolean to indicated if the user is authenticated, and a dictionary with user details.
    """
    auth_type_ = auth_type()
    if auth_type_ == AuthenticationType.TEST:
        # For testing purposes, we can return a fake user
        assert settings.auth.test.username is not None, "Test username must be set in settings"
        return AuthInfo(
            is_logged_in=True,
            user=UserInfo(
                login="test",
                display_name=settings.auth.test.username,
                url="https://example.com",
                token="",  # nosec
            ),
        )
    if auth_type_ == AuthenticationType.NONE:
        return AuthInfo(is_logged_in=False, user=UserInfo())
    if auth_type_ == AuthenticationType.SECRET:
        return AuthInfo(is_logged_in=await _is_auth_secret(request, response), user=UserInfo())
    if auth_type_ == AuthenticationType.GITHUB:
        return await _is_auth_user_github(request, response)

    return AuthInfo(is_logged_in=False, user=UserInfo())


async def get_access_context(
    auth_info: Annotated[AuthInfo, Depends(get_auth)],
    request: Request,
    response: Response,
) -> AccessContext:
    """
    Build an injectable access context for the current request.

    Usage:
        @app.get("/protected")
        async def protected_route(access_context: Annotated[AccessContext, Depends(get_access_context)]):
            await access_context.require_access(AuthConfig(github_repository="org/repo", github_access_type="admin"))
            return {"message": "You have access"}
    """
    return AccessContext(auth_info, request, response)


async def auth_required(auth_info: Annotated[AuthInfo, Depends(get_auth)]) -> None:
    """
    Check if the client is authenticated and raise an exception if not.

    Usage:
        @app.get("/protected")
        async def protected_route(_: Annotated[bool, Depends(auth_required)]):
            return {"message": "You are authenticated"}
    """
    if not auth_info.is_logged_in:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid secret (parameter, X-API-Key header or cookie)",
        )


class AuthenticationType(Enum):
    """The type of authentication."""

    # No Authentication configured
    NONE = 0
    # Authentication with a shared secret
    SECRET = 1
    # Authentication on GitHub and by having an access on a repository
    GITHUB = 2
    # Authentication used for testing purposes
    TEST = 3


def auth_type() -> AuthenticationType:
    """Get the authentication type."""
    if settings.auth.secret is not None:
        return AuthenticationType.SECRET

    if settings.auth.test.username is not None:
        return AuthenticationType.TEST

    has_client_id = settings.auth.github.client_id is not None
    has_client_secret = settings.auth.github.client_secret is not None
    has_repo = settings.auth.github.repository is not None

    if has_client_id and has_client_secret and has_repo:
        return AuthenticationType.GITHUB

    return AuthenticationType.NONE


async def startup(main_app: FastAPI) -> None:
    """Initialize the authentication system on application startup."""
    del main_app  # Unused argument

    if auth_type() == AuthenticationType.GITHUB and settings.auth.jwt.secret is None:
        message = "JWT secret is not set in the C2C__AUTH__JWT__SECRET environment variable"
        raise ValueError(message)


async def check_access(
    auth_info: Annotated[AuthInfo, Depends(get_auth)],
    auth_config: AuthConfig,
    request: Request | None = None,
    response: Response | None = None,
) -> bool:
    """
    Check if the user has access to the resource.

    If the authentication type is not GitHub, this function is equivalent to is_auth.
    """
    if not auth_info.is_logged_in:
        return False

    if await check_admin_access(auth_info, request=request, response=response):
        return True

    return await check_access_config(
        auth_info,
        auth_config,
        request=request,
        fastapi_response=response,
    )


async def check_admin_access(
    auth_info: Annotated[AuthInfo, Depends(get_auth)],
    request: Request | None = None,
    response: Response | None = None,
) -> bool:
    """Check if the user has admin access to the resource."""
    if not auth_info.is_logged_in:
        return False

    if auth_type() != AuthenticationType.GITHUB:
        return True

    return await check_access_config(
        auth_info,
        ADMIN_AUTH_CONFIG,
        request=request,
        fastapi_response=response,
    )


async def check_access_config(
    auth_info: Annotated[AuthInfo, Depends(get_auth)],
    auth_config: AuthConfig,
    request: Request | None = None,
    fastapi_response: Response | None = None,
) -> bool:
    """Check if the user has access to the resource."""
    if not auth_info.is_logged_in:
        return False

    repo_url = settings.auth.github.repo_url
    token = auth_info.user.token
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    async with (
        aiohttp.ClientSession() as session,
        session.get(
            f"{repo_url}/{auth_config.github_repository}",
            headers=headers,
        ) as github_response,
    ):
        if github_response.status == 401:
            if request is not None and fastapi_response is not None:
                _logout_user(request, fastapi_response, auth_info)
            else:
                auth_info.is_logged_in = False
                auth_info.user = UserInfo()
                auth_info.session_payload = None
            return False
        repository = await github_response.json()
        return not (
            "permissions" not in repository
            or repository["permissions"][auth_config.github_access_type] is not True
        )


async def require_access(
    auth_info: Annotated[AuthInfo, Depends(get_auth)],
    auth_config: AuthConfig,
    request: Request,
    response: Response,
) -> None:
    """
    FastAPI dependency that requires GitHub repository access.

    Usage:
        @app.get("/protected")
        async def protected_route(
            auth_info: Annotated[AuthInfo, Depends(get_auth)],
            request: Request,
            response: Response,
        ):
            await require_access(
                auth_info,
                AuthConfig(github_repository="org/repo", github_access_type="admin"),
                request,
                response,
            )
            return {"message": "You have access"}
    """
    access_context = AccessContext(auth_info, request, response)
    await access_context.require_access(auth_config)


async def require_admin_access(
    auth_info: Annotated[AuthInfo, Depends(get_auth)],
    request: Request,
    response: Response,
) -> None:
    """FastAPI dependency that requires admin access.

    Usage:
        @app.get("/admin_protected")
        async def admin_protected_route(_: Annotated[bool, Depends(require_admin_access)]):
            return {"message": "You have admin access"}
    """
    access_context = AccessContext(auth_info, request, response)
    await access_context.require_admin_access()


def is_enabled() -> bool:
    """Is the authentication enabled."""
    return auth_type() is not None


# Helper functions for FastAPI dependency injections


def _get_jwt_cookie_path(request: Request) -> str:
    """Get the path for the JWT cookie."""
    if settings.auth.jwt.cookie.path is not None:
        return settings.auth.jwt.cookie.path
    return request.url_for("c2c_index").path


def _set_jwt_cookie(
    request: Request,
    response: Response,
    payload: dict[str, Any],
    cookie_name: str = settings.auth.jwt.cookie.name,
    expiration: int = int(settings.auth.jwt.cookie.age.total_seconds()),
    path: str | None = None,
    same_site: Literal["lax", "strict", "none"] = settings.auth.jwt.cookie.same_site,
) -> None:
    """
    Set a JWT cookie in the response.

    Arguments
    ---------
        response: The response object to set the cookie on.
        payload: The payload to encode in the JWT.
        cookie_name: The name of the cookie to set.
        expiration: The expiration time in seconds for the cookie and the token.
        same_site: The SameSite attribute for the cookie.
    """

    if path is None:
        path = _get_jwt_cookie_path(request)

    jwt_payload = {
        **payload,
        "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=expiration),
        "iat": datetime.datetime.now(datetime.UTC),
    }
    response.set_cookie(
        key=cookie_name,
        value=jwt.encode(jwt_payload, settings.auth.jwt.secret, algorithm=settings.auth.jwt.algorithm),
        max_age=expiration,
        httponly=True,
        secure=settings.auth.jwt.cookie.secure,
        samesite=same_site,
        path=path,
    )


def _get_jwt_cookie(
    request: Request, cookie_name: str = settings.auth.jwt.cookie.name
) -> dict[str, Any] | None:
    """
    Get the JWT cookie from the request.

    Arguments
    ---------
        request: The request object containing cookies.
        cookie_name: The name of the cookie to retrieve.

    Returns
    -------
        The decoded JWT payload if the cookie exists and is valid, otherwise None.
    """

    if cookie_name not in request.cookies:
        return None

    return jwt.decode(
        request.cookies[cookie_name],
        settings.auth.jwt.secret,
        algorithms=[settings.auth.jwt.algorithm],
        options={"require": ["exp", "iat"]},  # Force presence of timestamps
    )


class _ErrorResponse(BaseModel):
    """Error response model for GitHub login callback."""

    error: str


router = APIRouter()

_auth_type = auth_type()
if _auth_type == AuthenticationType.SECRET:
    _LOG.warning(
        "It is recommended to use OAuth2 with GitHub login instead of the `C2C_SECRET` because it "
        "protects from brute force attacks and the access grant is personal and can be revoked.",
    )


if _auth_type == AuthenticationType.SECRET:

    @router.get("/login")
    async def login(
        request: Request,
        response: Response,
        secret: str | None = None,
        api_key: Annotated[str | None, Depends(api_key_header)] = None,
    ) -> dict[str, str]:
        """Login with a secret."""
        if secret is None and api_key is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing secret or X-API-Key header",
            )

        actual_secret = secret or api_key
        expected = settings.auth.secret
        if not expected or actual_secret != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret")

        # Set cookie
        _set_jwt_cookie(
            request,
            response,
            payload={
                "secret": actual_secret,
            },
        )
        return {"status": "success", "message": "Authentication successful"}

    @router.get("/logout")
    async def c2c_logout(request: Request, response: Response) -> dict[str, str]:
        """Logout by clearing the authentication cookie."""
        response.delete_cookie(key=settings.auth.jwt.cookie.name, path=_get_jwt_cookie_path(request))
        return {"status": "success", "message": "Logged out successfully"}


if _auth_type in (AuthenticationType.SECRET, AuthenticationType.GITHUB):

    @router.get("/status")
    async def c2c_auth_status(auth_info: Annotated[AuthInfo, Depends(get_auth)]) -> AuthInfo:
        """Get the authentication status."""
        return auth_info


if _auth_type == AuthenticationType.GITHUB:
    if not settings.auth.github.client_secret:
        _LOG.warning(
            "You are using GitHub authentication but the `AUTH_GITHUB_CLIENT_SECRET` is not set. "
            "This will work, but for security reasons, it is recommended to set this value.",
        )

    def _validated_came_from(
        request: Request,
        came_from: Annotated[str | None, Query()] = None,
    ) -> str | None:
        """Validate the 'came_from' parameter."""
        if came_from:
            if "\\" in came_from:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid 'came_from' parameter: contains backslashes",
                )
            came_from_parsed = urllib.parse.urlparse(came_from)

            if came_from_parsed.scheme and came_from_parsed.scheme not in ["http", "https"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid 'came_from' parameter: invalid scheme",
                )

            netloc = request.url.netloc
            allowed_netlocs: list[str] = []
            if netloc:
                allowed_netlocs.append(netloc)
            if came_from_parsed.netloc and came_from_parsed.netloc not in allowed_netlocs:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid 'came_from' parameter: not allowed host",
                )

            if not came_from_parsed.scheme or not came_from_parsed.netloc:
                if came_from_parsed.scheme:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid 'came_from' parameter: scheme without netloc",
                    )
                if came_from_parsed.netloc:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid 'came_from' parameter: netloc without scheme",
                    )
                # Relative URL, make it absolute
                base_url = str(request.base_url).rstrip("/")
                came_from = urllib.parse.urljoin(base_url, came_from)

        return came_from

    @router.get("/github/login")
    async def c2c_github_login(
        request: Request,
        response: Response,
        came_from: Annotated[str | None, Depends(_validated_came_from)] = None,
    ) -> RedirectResponse:
        """Initialize GitHub OAuth login flow."""
        base_callback_url = str(request.url_for("c2c_github_callback"))
        callback_url = (
            f"{base_callback_url}?{urllib.parse.urlencode({'came_from': came_from})}"
            if came_from
            else base_callback_url
        )

        proxy_url = settings.auth.github.proxy_url
        if proxy_url is not None:
            url = (
                proxy_url
                + ("&" if "?" in proxy_url else "?")
                + urllib.parse.urlencode({"came_from": callback_url})
            )
        else:
            url = callback_url

        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Build authorization URL manually
        auth_url = settings.auth.github.authorize_url
        client_id = settings.auth.github.client_id
        scope = settings.auth.github.scope

        if client_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GitHub client ID is not configured",
            )
        if scope is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GitHub scope is not configured",
            )

        params = {
            "client_id": client_id,
            "redirect_uri": url,
            "scope": scope,
            "state": state,
            "response_type": "code",
        }
        authorization_url = f"{auth_url}?{urllib.parse.urlencode(params)}"

        # State is used to prevent CSRF.
        _set_jwt_cookie(
            request,
            response,
            payload={
                "oauth_state": state,
            },
            cookie_name=settings.auth.github.state_cookie,
            expiration=int(settings.auth.github.state_cookie_age.total_seconds()),
            path=request.url_for("c2c_github_callback").path,
        )

        redirect_response = RedirectResponse(authorization_url)
        for value in response.headers.getlist("Set-Cookie"):
            redirect_response.headers.append("Set-Cookie", value)
        return redirect_response

    @router.get("/github/callback", response_model=_ErrorResponse)
    async def c2c_github_callback(
        request: Request,
        response: Response,
        came_from: Annotated[str | None, Depends(_validated_came_from)] = None,
        state: Annotated[str | None, Query()] = None,
        code: Annotated[str | None, Query()] = None,
        error: Annotated[str | None, Query()] = None,
    ) -> _ErrorResponse | RedirectResponse:
        """
        Do the post login operation authentication on GitHub.

        This will use the oauth token to get the user details from GitHub.
        And ask the GitHub rest API the information related to the configured repository
        to know which kind of access the user have.
        """
        try:
            state_payload = _get_jwt_cookie(
                request,
                settings.auth.github.state_cookie,
            )
            stored_state = state_payload.get("oauth_state") if state_payload else None
        except jwt.ExpiredSignatureError as jwt_exception:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return _ErrorResponse(error=f"Expired JWT cookie: {jwt_exception}")
        except jwt.InvalidTokenError as jwt_exception:
            response.status_code = status.HTTP_400_BAD_REQUEST
            _LOG.warning("Invalid JWT cookie", exc_info=jwt_exception)
            return _ErrorResponse(error=f"Invalid JWT cookie: {jwt_exception}")

        response.delete_cookie(
            key=settings.auth.github.state_cookie,
            path=request.url_for("c2c_github_callback").path,
        )

        # Verify state parameter to prevent CSRF attacks
        if stored_state is None:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return _ErrorResponse(error="Missing stored state parameter")
        if state is None:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return _ErrorResponse(error="Missing state parameter")
        if stored_state != state:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return _ErrorResponse(error="State parameter mismatch")

        if error:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return _ErrorResponse(error=error)

        if code is None:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return _ErrorResponse(error="Missing code parameter")

        callback_url = str(request.url_for("c2c_github_callback"))
        proxy_url = settings.auth.github.proxy_url
        if proxy_url is not None:
            url = (
                proxy_url
                + ("&" if "?" in proxy_url else "?")
                + urllib.parse.urlencode({"came_from": callback_url})
            )
        else:
            url = callback_url

        # Exchange code for token
        token_url = settings.auth.github.token_url
        client_id = settings.auth.github.client_id
        client_secret = settings.auth.github.client_secret

        # Prepare token exchange
        token_data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": url,
            "state": state,
        }
        headers = {"Accept": "application/json"}

        # Get token
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=token_data, headers=headers) as response_token:
                if response_token.status != 200:
                    response.status_code = status.HTTP_400_BAD_REQUEST
                    return _ErrorResponse(error=f"Failed to obtain token: {await response_token.text()}")
                token = await response_token.json()

            token_type = token.get("token_type")
            if token_type is None or token_type.lower() != "bearer":
                response.status_code = status.HTTP_400_BAD_REQUEST
                return _ErrorResponse(error=f"Invalid token_type: expected 'bearer', got {token_type!r}")

            # Get user info
            user_url = settings.auth.github.user_url
            headers = {
                "Authorization": f"Bearer {token['access_token']}",
                "Accept": "application/json",
            }

            async with session.get(user_url, headers=headers) as response_user:
                if response_user.status != 200:
                    response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                    return _ErrorResponse(error=f"Failed to get user info: {await response_user.text()}")
                user = await response_user.json()

        user_information = UserInfo(
            login=user["login"],
            display_name=user["name"],
            url=user["html_url"],
            token=token["access_token"],
        )
        payload = GitHubSessionPayload(**user_information.model_dump())
        _apply_token_lifetimes(payload, token)
        _set_jwt_cookie(request, response, payload=payload.model_dump(exclude_none=True))

        # Redirect to success page or front page
        redirect_after_login = came_from or str(request.url_for("c2c_index"))
        redirect_response = RedirectResponse(redirect_after_login)
        for value in response.headers.getlist("Set-Cookie"):
            redirect_response.headers.append("Set-Cookie", value)
        return redirect_response

    @router.get("/github/logout")
    async def c2c_github_logout(
        request: Request,
        came_from: Annotated[str | None, Depends(_validated_came_from)] = None,
    ) -> RedirectResponse:
        """Logout from GitHub authentication."""
        redirect_url = came_from or str(request.url_for("c2c_index"))
        redirect_response = RedirectResponse(redirect_url)
        redirect_response.delete_cookie(key=settings.auth.jwt.cookie.name, path=_get_jwt_cookie_path(request))
        return redirect_response
