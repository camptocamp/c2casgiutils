from app.schemas.response_schema import IGetResponseBase
from fastapi import APIRouter
from pydantic.generics import GenericModel

router = APIRouter()


class HelloResponse(GenericModel):
    """Response of the hello endpoint."""

    message: str = ""


@router.get("/hello")
async def hello() -> IGetResponseBase:
    """
    Get a hello message.
    """
    return HelloResponse(message="hello")
