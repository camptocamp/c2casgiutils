import logging

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from c2casgiutils import auth

_LOGGER = logging.getLogger(__name__)

router = APIRouter()


class HeadersClientInfoResponse(BaseModel):
    """Response of the root endpoint."""

    url: str
    base_url: str
    query_params: dict[str, str]
    path_params: str


class HeadersResponse(BaseModel):
    """Response of the root endpoint."""

    headers: dict[str, str]
    client_info: HeadersClientInfoResponse


@router.get("/", response_class=HTMLResponse)
async def c2c_headers(request: Request, response: HeadersResponse) -> HeadersResponse:
    """Return the headers of the request."""

    if not auth.check_access(request, response):
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
