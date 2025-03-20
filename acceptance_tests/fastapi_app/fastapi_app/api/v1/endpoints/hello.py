from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HelloResponse(BaseModel):
    """Response of the hello endpoint."""

    message: str = ""


@router.get("/hello")
async def hello() -> HelloResponse:
    """
    Get a hello message.
    """
    return HelloResponse(message="hello")
