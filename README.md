# Camptocamp ASGI Utils

This package provides a set of utilities to help you build ASGI applications with Python.

## Stack

Stack that we consider that the project uses:

- [FastAPI](https://github.com/fastapi/fastapi)
- [Health checks](https://pypi.org/project/fastapi-healthchecks/)
- [uviorn](https://www.uvicorn.org/)
- [SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Redis](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html)
- [Prometheus FastAPI Instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator)
- [Sentry](https://docs.sentry.io/platforms/python/integrations/fastapi/)

## Environment variables

See: https://github.com/camptocamp/c2casgiutils/blob/master/c2casgiutils/config.py

## Installation

```bash
pip install c2casgiutils
```

Add in your application:

```python

from c2casgiutils import broadcast

app.include_router(tools.router, prefix="/c2c")
app.mount("/c2c_static", tools.static_router)

@app.on_event("startup")
async def startup_event() -> None:
    """Initialize application on startup."""
    await tools.startup()
    await broadcast.setup_fastapi(app)

```

## Broadcasting

To use the broadcasting you should do something like this:

```python

from c2casgiutils import broadcast


class BroadcastResponse(BaseModel):
    """Response from broadcast endpoint."""

    result: list[dict[str, Any]] | None = None


echo_handler: Callable[[], Awaitable[list[BroadcastResponse] | None]] = None  # type: ignore[assignment]

# Create a handler that will receive broadcasts
async def echo_handler_() -> dict[str, Any]:
    """Echo handler for broadcast messages."""
    return {"message": "Broadcast echo"}


# Subscribe the handler to a channel on module import
@router.on_event("startup")
async def setup_broadcast_handlers() -> None:
    """Setups broadcast handlers when the API starts."""
    global echo_handler  # pylint: disable=global-statement
    echo_handler = await broadcast.decorate(echo_handler_, expect_answers=True)
```

Then you can use the `echo_handler` function you will have the response of all the registered applications.
