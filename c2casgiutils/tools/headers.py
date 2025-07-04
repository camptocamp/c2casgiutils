import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from c2casgiutils import auth

_LOGGER = logging.getLogger(__name__)

router = APIRouter()


class HeadersClientInfoResponse(BaseModel):
    """Response of the root endpoint."""

    url: str
    base_url: str
    query_params: dict[str, str]
    path_params: dict[str, Any]


class HeadersResponse(BaseModel):
    """Response of the root endpoint."""

    headers: dict[str, str]
    client_info: HeadersClientInfoResponse


async def _c2c_headers(request: Request, response: Response) -> HeadersResponse:
    """Return the headers of the request."""

    if not await auth.check_access(request, response):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    headers = dict(request.headers)
    if "authorization" in headers:
        headers["authorization"] = "*****"
    if "cookie" in headers:
        headers["cookie"] = "*****"

    return HeadersResponse(
        headers=headers,
        client_info=HeadersClientInfoResponse(
            url=str(request.url),
            base_url=str(request.base_url),
            query_params=dict(request.query_params),
            path_params=request.path_params,
        ),
    )


@router.get("/")
async def c2c_headers(request: Request, response: Response) -> HeadersResponse:
    """Return the headers of the request."""

    return await _c2c_headers(request, response)


@router.get("/{path}")
async def c2c_headers_path(request: Request, response: Response, path: str) -> HeadersResponse:
    """Return the headers of the request."""
    del path  # Unused path parameter, but required by FastAPI

    return await _c2c_headers(request, response)


@router.get("/{path_1}/{path_2}")
async def c2c_headers_path2(
    request: Request,
    response: Response,
    path_1: str,
    path_2: str,
) -> HeadersResponse:
    """Return the headers of the request."""
    del path_1, path_2  # Unused path parameters, but required by FastAPI

    return await _c2c_headers(request, response)
