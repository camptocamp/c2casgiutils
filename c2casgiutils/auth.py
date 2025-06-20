import hashlib
import logging
import secrets
import urllib.parse
from enum import Enum
from typing import Annotated, Any, TypedDict, cast
from uuid import UUID, uuid4

import aiohttp
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyCookie, APIKeyHeader, APIKeyQuery
from fastapi_sessions.backends.implementations import InMemoryBackend
from fastapi_sessions.frontends.implementations import CookieParameters, SessionCookie
from fastapi_sessions.session_verifier import SessionVerifier
from pydantic import BaseModel

from c2casgiutils.config import settings

_LOG = logging.getLogger(__name__)

# Security schemes
api_key_query = APIKeyQuery(name="secret", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_cookie = APIKeyCookie(name=settings.AUTH_COOKIE, auto_error=False)


# Session init start
class _SessionData(BaseModel):
    """Data stored in the session."""

    # The OAuth state used for CSRF protection
    # when using GitHub authentication.
    oauth_state: str


_cookie_params = CookieParameters()

# Uses UUID
_cookie = SessionCookie(
    cookie_name=settings.AUTH_SESSION_COOKIE,
    identifier="general_verifier",
    auto_error=True,
    secret_key=settings.AUTH_SESSION_SECRET,
    cookie_params=_cookie_params,
)

_backend = InMemoryBackend[UUID, _SessionData]()


class _BasicVerifier(SessionVerifier[UUID, _SessionData]):
    """A basic session verifier that checks if the session exists."""

    def __init__(
        self,
        *,
        identifier: str,
        auto_error: bool,
        backend: InMemoryBackend[UUID, _SessionData],
        auth_http_exception: HTTPException,
    ) -> None:
        """Initialize the session verifier."""
        self._identifier = identifier
        self._auto_error = auto_error
        self._backend = backend
        self._auth_http_exception = auth_http_exception

    @property
    def identifier(self) -> str:
        """The identifier of the session verifier."""
        return self._identifier

    @property
    def backend(self) -> InMemoryBackend[UUID, _SessionData]:
        """The backend used to store the session data."""
        return self._backend

    @property
    def auto_error(self) -> bool:
        """Whether to raise an HTTP exception if the session is not valid."""
        return self._auto_error

    @property
    def auth_http_exception(self) -> HTTPException:
        """The HTTP exception to raise if the session is not valid."""
        return self._auth_http_exception

    def verify_session(self, model: _SessionData) -> bool:
        """If the session exists, it is valid."""
        del model  # Unused, but required by the interface
        return True


_verifier = _BasicVerifier(
    identifier="general_verifier",
    auto_error=True,
    backend=_backend,
    auth_http_exception=HTTPException(status_code=403, detail="invalid session"),
)

# Session init end


class AuthConfig(TypedDict, total=False):
    """Configuration of the authentication."""

    # The repository to check access to (<organization>/<repository>).
    github_repository: str | None
    # The type of access to check (admin|push|pull).
    github_access_type: str | None


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


class UserDetails(TypedDict, total=False):
    """Details about the user authenticated with GitHub."""

    login: str
    name: str
    url: str
    token: str


async def _is_auth_secret(
    response: Response,
    query_secret: Annotated[str | None, Depends(api_key_query)] = None,
    header_secret: Annotated[str | None, Depends(api_key_header)] = None,
    cookie_secret: Annotated[str | None, Depends(api_key_cookie)] = None,
) -> bool:
    if not settings.AUTH_SECRET:
        return False

    expected = settings.AUTH_SECRET
    secret = query_secret or header_secret
    secret_hash = cookie_secret if secret is None else _hash_secret(secret)

    if secret_hash is not None:
        if secret_hash == "" or secret == "":  # nosec
            # Logout
            response.delete_cookie(key=settings.AUTH_COOKIE)
            return False
        if secret_hash != _hash_secret(expected):
            return False
        # Login or refresh the cookie
        response.set_cookie(
            key=settings.AUTH_COOKIE,
            value=secret_hash,
            max_age=settings.AUTH_COOKIE_AGE,
            httponly=True,
            secure=True,
            samesite="strict",
        )
        # Since this could be used from outside c2cwsgiutils views, we cannot set the path to c2c
        return True
    return False


async def _is_auth_user_github(request: Request) -> tuple[bool, UserDetails]:
    cookie_name = settings.AUTH_COOKIE
    cookie_ = request.cookies.get(cookie_name, "")
    if cookie_:
        try:
            return True, cast(
                "UserDetails",
                jwt.decode(
                    cookie_,
                    settings.AUTH_GITHUB_SECRET,
                    algorithms=["HS256"],
                ),
            )
        except jwt.exceptions.InvalidTokenError as e:
            _LOG.warning("Error on decoding JWT token: %s", e)
    return False, {}


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
    if settings.AUTH_SECRET != "":
        return AuthenticationType.SECRET

    has_client_id = settings.AUTH_GITHUB_CLIENT_ID != ""
    has_client_secret = settings.AUTH_GITHUB_CLIENT_SECRET != ""
    has_repo = settings.AUTH_GITHUB_REPOSITORY != ""
    secret = settings.AUTH_GITHUB_SECRET
    has_secret = len(secret) >= 16
    if secret and not has_secret:
        _LOG.error(
            "You set a too short secret (length: %i) to protect the admin page, it should have "
            "at lease a length of 16",
            len(secret),
        )

    if has_client_id and has_client_secret and has_repo and has_secret:
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
            "github_repository": (settings.AUTH_GITHUB_REPOSITORY if repo is None else repo),
            "github_access_type": (settings.AUTH_GITHUB_ACCESS_TYPE if access_type is None else access_type),
        },
    )


async def check_access_config(request: Request, auth_config: AuthConfig) -> bool:
    """Check if the user has access to the resource."""
    auth, user = await is_auth_user(request)
    if not auth:
        return False

    repo_url = settings.AUTH_GITHUB_REPO_URL
    token = user["token"]
    headers = {
        "Authorization": f"Bearer {token['access_token']}",
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


async def _github_login(request: Request, response: Response) -> dict[str, str]:
    """Get the view that start the authentication on GitHub."""
    params = dict(request.query_params)
    callback_url = request.url_for("c2c_github_callback")
    callback_url = str(callback_url)
    if "came_from" in params:
        callback_url = f"{callback_url}?came_from={params['came_from']}"

    proxy_url = settings.AUTH_GITHUB_PROXY_URL
    if proxy_url:
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
    auth_url = settings.AUTH_GITHUB_AUTH_URL
    client_id = settings.AUTH_GITHUB_CLIENT_ID
    scope = settings.AUTH_GITHUB_SCOPE

    params = {
        "client_id": client_id,
        "redirect_uri": url,
        "scope": scope,
        "state": state,
        "response_type": "code",
    }
    authorization_url = f"{auth_url}?{urllib.parse.urlencode(params)}"

    # State is used to prevent CSRF, keep this for later.
    if settings.AUTH_SESSION_SECRET:
        session = uuid4()
        data = _SessionData(oauth_state=state)
        await _backend.create(session, data)
        _cookie.attach_to_response(response, session)

    return RedirectResponse(authorization_url)


async def _github_login_callback(
    request: Request,
    response: Response,
    session_data: _SessionData = Depends(_verifier),
) -> dict[str, str]:
    """
    Do the post login operation authentication on GitHub.

    This will use the oauth token to get the user details from GitHub.
    And ask the GitHub rest API the information related to the configured repository
    to know which kind of access the user have.
    """
    stored_state = session_data.oauth_state if settings.AUTH_SESSION_SECRET else None
    received_state = request.query_params.get("state")
    code = request.query_params.get("code")

    # Verify state parameter to prevent CSRF attacks
    if settings.AUTH_SESSION_SECRET and stored_state != received_state:
        return {"error": "Invalid state parameter"}

    if request.query_params.get("error"):
        return {"error": request.query_params.get("error")}

    callback_url = str(request.url_for("c2c_github_callback"))
    proxy_url = settings.AUTH_GITHUB_PROXY_URL
    if proxy_url:
        url = (
            proxy_url
            + ("&" if "?" in proxy_url else "?")
            + urllib.parse.urlencode({"came_from": callback_url})
        )
    else:
        url = callback_url

    # Exchange code for token
    token_url = settings.AUTH_GITHUB_TOKEN_URL
    client_id = settings.AUTH_GITHUB_CLIENT_ID
    client_secret = settings.AUTH_GITHUB_CLIENT_SECRET

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
                return {"error": f"Failed to obtain token: {await response_token.text()}"}
            token = await response_token.json()

        # Get user info
        user_url = settings.AUTH_GITHUB_USER_URL
        headers = {
            "Authorization": f"Bearer {token['access_token']}",
            "Accept": "application/json",
        }

        async with session.get(user_url, headers=headers) as response_user:
            if response_user.status != 200:
                return {"error": f"Failed to get user info: {await response_user.text()}"}
            user = await response_user.json()

    user_information: UserDetails = {
        "login": user["login"],
        "name": user["name"],
        "url": user["html_url"],
        "token": token,
    }
    response.set_cookie(
        settings.AUTH_COOKIE,
        jwt.encode(
            cast("dict[str, Any]", user_information),
            settings.AUTH_GITHUB_SECRET,
            algorithm="HS256",
        ),
        max_age=settings.AUTH_COOKIE_AGE,
        httponly=True,
        secure=True,
        samesite="strict",
    )

    # Redirect to success page or front page
    redirect_after_login = request.cookies.get("c2c-auth-redirect", "/")
    return RedirectResponse(redirect_after_login)


async def _github_logout(request: Request, response: Response) -> dict[str, Any]:
    """Logout the user."""
    response.delete_cookie(key=settings.AUTH_COOKIE)
    response.delete_cookie(
        key=settings.AUTH_COOKIE,
    )

    redirect_url = request.query_params.get("came_from", "/")
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
        expected = settings.AUTH_SECRET
        if not expected or _hash_secret(actual_secret) != _hash_secret(expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret")

        # Set cookie
        response.set_cookie(
            key=settings.AUTH_COOKIE,
            value=_hash_secret(actual_secret),
            max_age=settings.AUTH_COOKIE_AGE,
            httponly=True,
            secure=True,
            samesite="strict",
        )
        return {"status": "success", "message": "Authentication successful"}

    @router.get("/logout")
    async def c2c_logout(response: Response) -> dict[str, str]:
        """Logout by clearing the authentication cookie."""
        response.delete_cookie(key=settings.AUTH_COOKIE)
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
    if not settings.AUTH_GITHUB_CLIENT_SECRET:
        _LOG.warning(
            "You are using GitHub authentication but the `AUTH_GITHUB_CLIENT_SECRET` is not set. "
            "This will work, but for security reasons, it is recommended to set this value.",
        )

    @router.get("/github/login")
    async def c2c_github_login(request: Request, response: Response) -> dict[str, str]:
        """Initialize GitHub OAuth login flow."""
        return await _github_login(request, response)

    @router.get("/github/callback")
    async def c2c_github_callback(request: Request, response: Response) -> dict[str, str]:
        """Handle GitHub OAuth callback."""
        return await _github_login_callback(request, response)

    @router.get("/github/logout")
    async def c2c_github_logout(request: Request, response: Response) -> dict[str, str]:
        """Logout from GitHub authentication."""
        return await _github_logout(request, response)
