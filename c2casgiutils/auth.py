import hashlib
import logging
import os
import urllib.parse
from enum import Enum
from typing import Annotated, Any, TypedDict, cast

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyCookie, APIKeyHeader, APIKeyQuery
from requests_oauthlib import OAuth2Session

_LOG = logging.getLogger(__name__)

_COOKIE_AGE = 7 * 24 * 3600
_SECRET_ENV = "C2C_SECRET"  # noqa: S105, secret # nosec
_GITHUB_REPOSITORY_ENV = "C2C_AUTH_GITHUB_REPOSITORY"
_GITHUB_ACCESS_TYPE_ENV = "C2C_AUTH_GITHUB_ACCESS_TYPE"
_GITHUB_AUTH_URL_ENV = "C2C_AUTH_GITHUB_AUTH_URL"
_GITHUB_TOKEN_URL_ENV = "C2C_AUTH_GITHUB_TOKEN_URL"  # noqa: S105, secret # nosec
_GITHUB_USER_URL_ENV = "C2C_AUTH_GITHUB_USER_URL"
_GITHUB_REPO_URL_ENV = "C2C_AUTH_GITHUB_REPO_URL"
_GITHUB_CLIENT_ID_ENV = "C2C_AUTH_GITHUB_CLIENT_ID"
_GITHUB_CLIENT_SECRET_ENV = "C2C_AUTH_GITHUB_CLIENT_SECRET"  # noqa: S105, secret # nosec
_GITHUB_SCOPE_ENV = "C2C_AUTH_GITHUB_SCOPE"
# To be able to use private repository
_GITHUB_SCOPE_DEFAULT = "repo"
_GITHUB_AUTH_COOKIE_ENV = "C2C_AUTH_GITHUB_COOKIE"
_GITHUB_AUTH_SECRET_ENV = "C2C_AUTH_GITHUB_SECRET"  # noqa: S105, secret # nosec
_GITHUB_AUTH_PROXY_URL_ENV = "C2C_AUTH_GITHUB_PROXY_URL"
_USE_SESSION_ENV = "C2C_USE_SESSION"


_LOG = logging.getLogger(__name__)


# Security schemes
api_key_query = APIKeyQuery(name="secret", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_cookie = APIKeyCookie(name=_SECRET_ENV, auto_error=False)


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
    if _SECRET_ENV not in os.environ:
        return False

    expected = os.environ[_SECRET_ENV]
    secret = query_secret or header_secret
    secret_hash = cookie_secret if secret is None else _hash_secret(secret)

    if secret_hash is not None:
        if secret_hash == "" or secret == "":  # nosec
            # Logout
            response.delete_cookie(key=_SECRET_ENV)
            return False
        if secret_hash != _hash_secret(expected):
            return False
        # Login or refresh the cookie
        response.set_cookie(
            key=_SECRET_ENV,
            value=secret_hash,
            max_age=_COOKIE_AGE,
            httponly=True,
            secure=True,
            samesite="strict",
        )
        # Since this could be used from outside c2cwsgiutils views, we cannot set the path to c2c
        return True
    return False


async def _is_auth_user_github(request: Request) -> tuple[bool, UserDetails]:
    cookie_name = os.environ.get(_GITHUB_AUTH_COOKIE_ENV, "c2c-auth-jwt")
    cookie = request.cookies.get(cookie_name, "")
    if cookie:
        try:
            return True, cast(
                "UserDetails",
                jwt.decode(
                    cookie,
                    os.environ.get(_GITHUB_AUTH_SECRET_ENV),
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
    if os.environ.get(_SECRET_ENV, "") != "":
        return AuthenticationType.SECRET

    has_client_id = os.environ.get(_GITHUB_CLIENT_ID_ENV, "") != ""
    has_client_secret = os.environ.get(_GITHUB_CLIENT_SECRET_ENV, "") != ""
    has_repo = os.environ.get(_GITHUB_REPOSITORY_ENV, "") != ""
    secret = os.environ.get(_GITHUB_AUTH_SECRET_ENV, "")
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
            "github_repository": (os.environ.get(_GITHUB_REPOSITORY_ENV, "") if repo is None else repo),
            "github_access_type": (
                os.environ.get(_GITHUB_ACCESS_TYPE_ENV, "pull") if access_type is None else access_type
            ),
        },
    )


async def check_access_config(request: Request, auth_config: AuthConfig) -> bool:
    """Check if the user has access to the resource."""
    auth, user = await is_auth_user(request)
    if not auth:
        return False

    oauth = OAuth2Session(
        os.environ.get(_GITHUB_CLIENT_ID_ENV, ""),
        scope=[os.environ.get(_GITHUB_SCOPE_ENV, _GITHUB_SCOPE_DEFAULT)],
        redirect_uri=request.route_url("c2c_github_callback"),
        token=user["token"],
    )

    repo_url = os.environ.get(_GITHUB_REPO_URL_ENV, "https://api.github.com/repos")
    repository = oauth.get(f"{repo_url}/{auth_config.get('github_repository')}").json()
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


def _github_login(request: Request) -> dict[str, str]:
    """Get the view that start the authentication on GitHub."""
    params = dict(request.query_params)
    callback_url = request.url_for("github_callback")
    callback_url = str(callback_url)
    if "came_from" in params:
        callback_url = f"{callback_url}?came_from={params['came_from']}"

    proxy_url = os.environ.get(_GITHUB_AUTH_PROXY_URL_ENV, "")
    if proxy_url:
        url = (
            proxy_url
            + ("&" if "?" in proxy_url else "?")
            + urllib.parse.urlencode({"came_from": callback_url})
        )
    else:
        url = callback_url
    oauth = OAuth2Session(
        os.environ.get(_GITHUB_CLIENT_ID_ENV, ""),
        scope=[os.environ.get(_GITHUB_SCOPE_ENV, _GITHUB_SCOPE_DEFAULT)],
        redirect_uri=url,
    )
    authorization_url, state = oauth.authorization_url(
        os.environ.get(
            _GITHUB_AUTH_URL_ENV,
            "https://github.com/login/oauth/authorize",
        ),
    )
    use_session = os.environ.get(_USE_SESSION_ENV, "").lower() == "true"
    # State is used to prevent CSRF, keep this for later.
    if use_session:
        request.session["oauth_state"] = state
    raise RedirectResponse(authorization_url, headers=request.response.headers)


async def _github_login_callback(request: Request, response: Response) -> dict[str, str]:
    """
    Do the post login operation authentication on GitHub.

    This will use the oauth token to get the user details from GitHub.
    And ask the GitHub rest API the information related to the configured repository
    to know which kind of access the user have.
    """
    use_session = os.environ.get(_USE_SESSION_ENV, "").lower() == "true"
    state = request.session.get("oauth_state") if use_session else None

    callback_url = str(request.url_for("github_callback"))
    proxy_url = os.environ.get(_GITHUB_AUTH_PROXY_URL_ENV, "")
    if proxy_url:
        url = (
            proxy_url
            + ("&" if "?" in proxy_url else "?")
            + urllib.parse.urlencode({"came_from": callback_url})
        )
    else:
        url = callback_url
    oauth = OAuth2Session(
        os.environ.get(_GITHUB_CLIENT_ID_ENV, ""),
        scope=[os.environ.get(_GITHUB_SCOPE_ENV, _GITHUB_SCOPE_DEFAULT)],
        redirect_uri=url,
        state=state,
    )

    if request.query_params.get("error"):
        return {"error": request.query_params.get("error")}

    token = oauth.fetch_token(
        token_url=os.environ.get(
            _GITHUB_TOKEN_URL_ENV,
            "https://github.com/login/oauth/access_token",
        ),
        authorization_response=str(request.url),
        client_secret=os.environ.get(_GITHUB_CLIENT_SECRET_ENV, ""),
    )

    user = oauth.get(
        os.environ.get(
            _GITHUB_USER_URL_ENV,
            "https://api.github.com/user",
        ),
    ).json()

    user_information: UserDetails = {
        "login": user["login"],
        "name": user["name"],
        "url": user["html_url"],
        "token": token,
    }
    response.set_cookie(
        os.environ.get(
            _GITHUB_AUTH_COOKIE_ENV,
            "c2c-auth-jwt",
        ),
        jwt.encode(
            cast("dict[str, Any]", user_information),
            os.environ.get(
                _GITHUB_AUTH_SECRET_ENV,
            ),
            algorithm="HS256",
        ),
        max_age=_COOKIE_AGE,
        httponly=True,
        secure=True,
        samesite="strict",
    )

    # Redirect to success page or front page
    redirect_after_login = request.cookies.get("c2c-auth-redirect", "/")
    return RedirectResponse(redirect_after_login)


async def _github_logout(request: Request, response: Response) -> dict[str, Any]:
    """Logout the user."""
    response.delete_cookie(key=_SECRET_ENV)
    response.delete_cookie(
        key=os.environ.get(_GITHUB_AUTH_COOKIE_ENV, "c2c-auth-jwt"),
    )

    redirect_url = request.query_params.get("came_from", "/")
    return RedirectResponse(redirect_url)


def get_auth_router() -> APIRouter:
    """
    Get a FastAPI router with authentication routes.

    Usage:
        from fastapi import FastAPI
        from c2casgiutils.auth import get_auth_router

        app = FastAPI()
        auth_router = get_auth_router()
        app.include_router(auth_router, prefix="/auth")
    """
    router = APIRouter()

    auth_type_ = auth_type()
    if auth_type_ == AuthenticationType.SECRET:
        _LOG.warning(
            "It is recommended to use OAuth2 with GitHub login instead of the `C2C_SECRET` because it "
            "protects from brute force attacks and the access grant is personal and can be revoked.",
        )

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
        expected = os.environ.get(_SECRET_ENV)
        if not expected or _hash_secret(actual_secret) != _hash_secret(expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret")

        # Set cookie
        response.set_cookie(
            key=_SECRET_ENV,
            value=_hash_secret(actual_secret),
            max_age=_COOKIE_AGE,
            httponly=True,
            secure=True,
            samesite="strict",
        )
        return {"status": "success", "message": "Authentication successful"}

    @router.get("/logout")
    async def logout(response: Response) -> dict[str, str]:
        """Logout by clearing the authentication cookie."""
        response.delete_cookie(key=_SECRET_ENV)
        return {"status": "success", "message": "Logged out successfully"}

    @router.get("/status")
    async def auth_status(request: Request, response: Response) -> dict[str, Any]:
        """Get the authentication status."""
        auth, user = await is_auth_user(request, response)
        if auth:
            return {"authenticated": True, "user": user}
        return {"authenticated": False}

    if os.environ.get(_GITHUB_CLIENT_ID_ENV) and os.environ.get(_GITHUB_AUTH_SECRET_ENV):

        @router.get("/github/login")
        async def github_login(request: Request) -> dict[str, str]:
            """Initialize GitHub OAuth login flow."""
            return _github_login(request)

        @router.get("/github/callback")
        async def github_callback(request: Request, response: Response) -> dict[str, str]:
            """Handle GitHub OAuth callback."""
            return await _github_login_callback(request, response)

        @router.get("/github/logout")
        async def github_logout(request: Request, response: Response) -> dict[str, str]:
            """Logout from GitHub authentication."""
            return await _github_logout(request, response)

    return router
