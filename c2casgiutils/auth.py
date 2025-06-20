import datetime
import logging
import secrets
import urllib.parse
from enum import Enum
from typing import Annotated, Any, TypedDict, cast

import aiohttp
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyHeader, APIKeyQuery
from pydantic import BaseModel

from c2casgiutils.config import settings

_LOG = logging.getLogger(__name__)

# Security schemes
api_key_query = APIKeyQuery(name="secret", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthConfig(TypedDict, total=False):
    """Configuration of the authentication."""

    # The repository to check access to (<organization>/<repository>).
    github_repository: str | None
    # The type of access to check (admin|push|pull).
    github_access_type: str | None


class UserDetails(TypedDict, total=False):
    """Details about the user authenticated with GitHub."""

    login: str
    name: str
    url: str
    token: str


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
            secret_payload = _get_jwt_cookie(request, settings.auth.cookie)
            if secret_payload is not None:
                secret = secret_payload.get("secret")
        except jwt.ExpiredSignatureError:
            _LOG.warning("Expired JWT cookie")
        except jwt.InvalidTokenError as jwt_exception:
            _LOG.warning("Invalid JWT cookie", exc_info=jwt_exception)

    if secret is not None:
        if secret == "":  # nosec
            # Logout
            response.delete_cookie(key=settings.auth.cookie)
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


async def _is_auth_user_github(request: Request) -> tuple[bool, UserDetails]:
    if settings.auth.test.username is not None:
        # For testing purposes, we can return a fake user
        return True, {
            "login": "test",
            "name": settings.auth.test.username,
            "url": "https://example.com",
            "token": "",
        }
    try:
        user_payload = _get_jwt_cookie(
            request,
            settings.auth.cookie,
        )
    except jwt.ExpiredSignatureError as jwt_exception:
        raise HTTPException(401, "Expired session") from jwt_exception
    except jwt.InvalidTokenError as jwt_exception:
        raise HTTPException(401, "Invalid session") from jwt_exception
    return user_payload is not None, cast(
        "UserDetails",
        user_payload,
    )


async def is_auth_user(request: Request, response: Response | None = None) -> tuple[bool, UserDetails]:
    """
    Check if the client is authenticated.

    Returns: boolean to indicated if the user is authenticated, and a dictionary with user details.
    """
    auth_type_ = auth_type()
    if auth_type_ == AuthenticationType.NONE:
        return False, {}
    if auth_type_ == AuthenticationType.SECRET:
        if response is None:
            # If no response is provided, we can't set cookies
            return False, {}
        return await _is_auth_secret(request, response), {}
    if auth_type_ == AuthenticationType.GITHUB:
        return await _is_auth_user_github(request)

    return False, {}


async def is_auth(request: Request, response: Response | None = None) -> bool:
    """Check if the client is authenticated."""
    auth, _ = await is_auth_user(request, response)
    return auth


async def auth_required(request: Request, response: Response | None = None) -> bool:
    """
    Check if the client is authenticated and raise an exception if not.

    Usage:
        @app.get("/protected")
        async def protected_route(auth: Annotated[bool, Depends(auth_required)]):
            return {"message": "You are authenticated"}
    """
    if not await is_auth(request, response):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid secret (parameter, X-API-Key header or cookie)",
        )
    return True


class AuthenticationType(Enum):
    """The type of authentication."""

    # No Authentication configured
    NONE = 0
    # Authentication with a shared secret
    SECRET = 1
    # Authentication on GitHub and by having an access on a repository
    GITHUB = 2


def auth_type() -> AuthenticationType | None:
    """Get the authentication type."""
    if settings.auth.secret is not None:
        return AuthenticationType.SECRET

    has_client_id = settings.auth.github.client_id is not None
    has_client_secret = settings.auth.github.client_secret is not None
    has_repo = settings.auth.github.repository is not None

    if has_client_id and has_client_secret and has_repo:
        return AuthenticationType.GITHUB

    return AuthenticationType.NONE


async def check_access(
    request: Request,
    response: Response | None = None,
    repo: str | None = None,
    access_type: str | None = None,
) -> bool:
    """
    Check if the user has access to the resource.

    If the authentication type is not GitHub, this function is equivalent to is_auth.

    Arguments:
        request: is the request object.
        response: optional response object to set cookies.
        repo: is the repository to check access to (<organization>/<repository>).
        access_type: is the type of access to check (admin|push|pull).

    """
    if not await is_auth(request, response):
        return False

    if auth_type() != AuthenticationType.GITHUB:
        return True

    return await check_access_config(
        request,
        {
            "github_repository": (settings.auth.github.repository if repo is None else repo),
            "github_access_type": (settings.auth.github.access_type if access_type is None else access_type),
        },
    )


async def check_access_config(request: Request, auth_config: AuthConfig) -> bool:
    """Check if the user has access to the resource."""
    auth, user = await is_auth_user(request)
    if not auth:
        return False

    repo_url = settings.auth.github.repo_url
    token = user["token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    async with (
        aiohttp.ClientSession() as session,
        session.get(
            f"{repo_url}/{auth_config.get('github_repository')}",
            headers=headers,
        ) as response,
    ):
        repository = await response.json()
        return not (
            "permissions" not in repository
            or repository["permissions"][auth_config.get("github_access_type")] is not True
        )


async def require_access(
    request: Request,
    response: Response | None = None,
    repo: str | None = None,
    access_type: str | None = None,
) -> bool:
    """
    FastAPI dependency that requires GitHub repository access.

    Usage:
        @app.get("/admin")
        async def admin_route(access: Annotated[bool, Depends(
            lambda req, res: require_access(req, res, "org/repo", "admin")
        )]):
            return {"message": "You have admin access"}
    """
    if not await check_access(request, response, repo, access_type):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this resource",
        )
    return True


def is_enabled() -> bool:
    """Is the authentication enabled."""
    return auth_type() is not None


# Helper functions for FastAPI dependency injections


async def auth_dependency(request: Request, response: Response | None = None) -> tuple[bool, UserDetails]:
    """
    Provide authentication information.

    Usage:
        @app.get("/")
        async def root(auth_info: Annotated[tuple, Depends(auth_dependency)]):
            is_authenticated, user_details = auth_info
            if is_authenticated:
                return {"message": f"Hello {user_details.get('name', 'User')}"}
            return {"message": "Hello Anonymous"}
    """
    return await is_auth_user(request, response)


def _set_jwt_cookie(
    request: Request,
    response: Response,
    payload: dict[str, Any],
    cookie_name: str = settings.auth.cookie,
    expiration: int = settings.auth.cookie_age,
    path: str | None = None,
) -> None:
    """
    Set a JWT cookie in the response.

    Arguments
    ---------
        response: The response object to set the cookie on.
        payload: The payload to encode in the JWT.
        cookie_name: The name of the cookie to set.
        expiration: The expiration time in seconds for the cookie and the token.
    """
    if path is None:
        if settings.auth.jwt.cookie.path is not None:
            path = settings.auth.jwt.cookie.path
        else:
            path = request.url_for("c2c_index").path

    jwt_payload = {
        **payload,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expiration),
        "iat": datetime.datetime.now(datetime.timezone.utc),
    }
    response.set_cookie(
        key=cookie_name,
        value=jwt.encode(jwt_payload, settings.auth.jwt.secret, algorithm=settings.auth.jwt.algorithm),
        max_age=expiration,
        httponly=True,
        secure=settings.auth.jwt.cookie.secure,
        samesite=settings.auth.jwt.cookie.same_site,
        path=path,
    )


def _get_jwt_cookie(request: Request, cookie_name: str) -> dict[str, Any] | None:
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
    return cast(
        "dict[str, Any]",
        jwt.decode(
            request.cookies[cookie_name],
            settings.auth.jwt.secret,
            algorithms=[settings.auth.jwt.algorithm],
            options={"require": ["exp", "iat"]},  # Force presence of timestamps
        ),
    )


async def _github_login(request: Request, response: Response) -> RedirectResponse:
    """Get the view that start the authentication on GitHub."""
    params = dict(request.query_params)
    callback_url = str(request.url_for("c2c_github_callback"))
    if "came_from" in params:
        callback_url = f"{callback_url}?came_from={params['came_from']}"

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
        expiration=settings.auth.github.state_cookie_age,
        path=request.url_for("c2c_github_callback").path,
    )

    redirect_response = RedirectResponse(authorization_url)
    for value in response.headers.getlist("Set-Cookie"):
        redirect_response.headers.append("Set-Cookie", value)
    return redirect_response


class _ErrorResponse(BaseModel):
    """Error response model for GitHub login callback."""

    error: str


async def _github_login_callback(
    request: Request,
    response: Response,
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

    received_state = request.query_params.get("state")
    code = request.query_params.get("code")
    response.delete_cookie(
        key=settings.auth.github.state_cookie,
    )

    # Verify state parameter to prevent CSRF attacks
    if stored_state != received_state:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return _ErrorResponse(error="Invalid state parameter")

    if request.query_params.get("error"):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return _ErrorResponse(error=request.query_params.get("error", "Missing error"))

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
        "state": received_state,
    }
    headers = {"Accept": "application/json"}

    # Get token
    async with aiohttp.ClientSession() as session:
        async with session.post(token_url, data=token_data, headers=headers) as response_token:
            if response_token.status != 200:
                response.status_code = status.HTTP_400_BAD_REQUEST
                return _ErrorResponse(error=f"Failed to obtain token: {await response_token.text()}")
            token = await response_token.json()

        # Get user info
        user_url = settings.auth.github.user_url
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        async with session.get(user_url, headers=headers) as response_user:
            if response_user.status != 200:
                response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                return _ErrorResponse(error=f"Failed to get user info: {await response_user.text()}")
            user = await response_user.json()

    user_information: UserDetails = {
        "login": user["login"],
        "name": user["name"],
        "url": user["html_url"],
        "token": token,
    }
    _set_jwt_cookie(request, response, payload=user_information)  # type: ignore[arg-type]

    # Redirect to success page or front page
    redirect_after_login = request.query_params.get("came_from", str(request.url_for("c2c_index")))
    redirect_response = RedirectResponse(redirect_after_login)
    for value in response.headers.getlist("Set-Cookie"):
        redirect_response.headers.append("Set-Cookie", value)
    return redirect_response


async def _github_logout(request: Request, response: Response) -> RedirectResponse:
    """Logout the user."""
    response.delete_cookie(key=settings.auth.cookie)

    redirect_url = request.query_params.get("came_from", str(request.url_for("c2c_index")))
    return RedirectResponse(redirect_url)


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
    async def c2c_logout(response: Response) -> dict[str, str]:
        """Logout by clearing the authentication cookie."""
        response.delete_cookie(key=settings.auth.cookie)
        return {"status": "success", "message": "Logged out successfully"}


if _auth_type in (AuthenticationType.SECRET, AuthenticationType.GITHUB):

    @router.get("/status")
    async def c2c_auth_status(request: Request, response: Response) -> dict[str, Any]:
        """Get the authentication status."""
        auth, user = await is_auth_user(request, response)
        if auth:
            return {"authenticated": True, "user": user}
        return {"authenticated": False}


if _auth_type == AuthenticationType.GITHUB:
    if not settings.auth.github.client_secret:
        _LOG.warning(
            "You are using GitHub authentication but the `AUTH_GITHUB_CLIENT_SECRET` is not set. "
            "This will work, but for security reasons, it is recommended to set this value.",
        )

    @router.get("/github/login")
    async def c2c_github_login(request: Request, response: Response) -> RedirectResponse:
        """Initialize GitHub OAuth login flow."""
        return await _github_login(request, response)

    @router.get("/github/callback", response_model=_ErrorResponse)
    async def c2c_github_callback(request: Request, response: Response) -> _ErrorResponse | RedirectResponse:
        """Handle GitHub OAuth callback."""
        return await _github_login_callback(request, response)

    @router.get("/github/logout")
    async def c2c_github_logout(request: Request, response: Response) -> RedirectResponse:
        """Logout from GitHub authentication."""
        return await _github_logout(request, response)
