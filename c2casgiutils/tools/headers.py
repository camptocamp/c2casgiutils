import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
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


async def _c2c_headers(request: Request) -> HeadersResponse:
    """Get the headers of the request."""

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
async def c2c_headers(
    request: Request,
    _: Annotated[None, Depends(auth.require_admin_access)],
) -> HeadersResponse:
    """Get the headers of the request."""

    return await _c2c_headers(request)


@router.get("/{path}")
async def c2c_headers_path(
    request: Request,
    path: str,
    param: Annotated[str | None, Query(description="An optional query parameter")] = None,
    _: Annotated[None, Depends(auth.require_admin_access)] = None,
) -> HeadersResponse:
    """Get the headers of the request with one path."""
    del path, param  # Unused path parameter, but required by FastAPI

    return await _c2c_headers(request)


@router.get("/{path_1}/{path_2}")
async def c2c_headers_path2(
    request: Request,
    path_1: str,
    path_2: str,
    param_1: Annotated[str | None, Query(description="An optional query parameter")] = None,
    param_2: Annotated[str | None, Query(description="A second optional query parameter")] = None,
    _: Annotated[None, Depends(auth.require_admin_access)] = None,
) -> HeadersResponse:
    """Get the headers of the request with two path."""
    del path_1, path_2, param_1, param_2  # Unused path parameters, but required by FastAPI

    return await _c2c_headers(request)
