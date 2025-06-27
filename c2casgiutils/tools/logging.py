import logging
from collections.abc import Generator
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel

from c2casgiutils import auth, broadcast, config, redis_utils

router = APIRouter()


class LevelResponse(BaseModel):
    """Response for the logging level endpoint."""

    name: str
    level: str
    effective_level: str


class OverrideResponse(BaseModel):
    """Response for the logging level endpoint."""

    name: str
    level: str


class OverridesResponse(BaseModel):
    """Response for the logging level endpoint."""

    overrides: list[OverrideResponse]


_LOGGER = logging.getLogger(__name__)


@router.get("/level", response_class=LevelResponse)
async def c2c_logging_level(
    request: Request,
    response: Response,
    name: Annotated[str, Query()],
    level: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    """Change the logging level."""
    if not auth.check_access(request, response):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    logger = logging.getLogger(name)
    if level is not None:
        _LOGGER.critical(
            "Logging of %s changed from %s to %s",
            name,
            logging.getLevelName(logger.level),
            level,
        )
        _set_level(name=name, level=level)
        _store_override(name, level)
    return LevelResponse(
        name=name,
        level=logging.getLevelName(logger.level),
        effective_level=logging.getLevelName(logger.getEffectiveLevel()),
    )


@router.get("/overrides", response_class=OverridesResponse)
async def c2c_logging_overrides(
    request: Request,
    response: Response,
) -> dict[str, Any]:
    """Change the logging level."""
    if not auth.check_access(request, response):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return OverridesResponse(overrides=_list_overrides())


def __set_level(name: str, level: str) -> bool:
    logging.getLogger(name).setLevel(level)
    return True


_set_level = broadcast.decorator(expect_answers=True)(__set_level)


@router.on_event("startup")
async def _restore_overrides() -> None:
    """
    Restore logging overrides from Redis.

    Should be called on application startup to ensure that any logging level overrides.
    """
    try:
        for name, level in _list_overrides():
            _LOGGER.debug("Restoring logging level override for %s: %s", name, level)
            logging.getLogger(name).setLevel(level)
    except ImportError:
        pass  # don't have redis
    except Exception:  # pylint: disable=broad-exception-caught
        # survive an error there. Logging levels is not business critical...
        _LOGGER.warning("Cannot restore logging levels", exc_info=True)


def _store_override(name: str, level: str) -> None:
    try:
        master, _, _ = redis_utils.get()
        if master:
            master.set(config.settings.tools.logging.redis_prefix + name, level)
    except ImportError:
        pass


def _list_overrides() -> Generator[OverrideResponse, None, None]:
    _, slave, _ = redis_utils.get()
    if slave is not None:
        for key in slave.scan_iter(config.settings.tools.logging.redis_prefix + "*"):
            level = slave.get(key)
            name = key[len(config.settings.tools.logging.redis_prefix) :]
            if level is not None:
                yield OverrideResponse(name=name, level=level)
