import logging
from collections.abc import AsyncGenerator
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, FastAPI, Query
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


class _SetLevelFunction(Protocol):
    """Set the logging level for a given logger name."""

    async def __call__(self, name: str, level: str) -> list[bool]: ...


_set_level: _SetLevelFunction


@router.get("/level")
async def c2c_logging_level(
    name: Annotated[str, Query(description="Name of the logger to get the level for")],
    _: Annotated[None, Depends(auth.require_admin_access)],
) -> LevelResponse:
    """Get the logging level."""

    logger = logging.getLogger(name)
    return LevelResponse(
        name=name,
        level=logging.getLevelName(logger.level),
        effective_level=logging.getLevelName(logger.getEffectiveLevel()),
    )


class _SetLevel(BaseModel):
    name: str
    level: str


@router.post("/level")
async def c2c_logging_set_level(
    level: _SetLevel,
    _: Annotated[None, Depends(auth.require_admin_access)],
) -> LevelResponse:
    """Change the logging level."""

    logger = logging.getLogger(level.name)
    _LOGGER.info(
        "Logging of %s changed from %s to %s",
        level.name,
        logging.getLevelName(logger.level),
        level.level,
    )
    await _set_level(name=level.name, level=level.level)
    await _store_override(level.name, level.level)
    return LevelResponse(
        name=level.name,
        level=logging.getLevelName(logger.level),
        effective_level=logging.getLevelName(logger.getEffectiveLevel()),
    )


@router.get("/overrides")
async def c2c_logging_overrides(
    _: Annotated[None, Depends(auth.require_admin_access)],
) -> OverridesResponse:
    """Get the logging overrides."""

    return OverridesResponse(overrides=[e async for e in _list_overrides()])


async def __set_level(name: str, level: str) -> bool:
    logging.getLogger(name).setLevel(level)
    return True


async def _restore_overrides() -> None:
    """
    Restore logging overrides from Redis.

    Should be called on application startup to ensure that any logging level overrides.
    """
    try:
        async for override in _list_overrides():
            _LOGGER.info("Restoring logging level override for %s: %s", override.name, override.level)
            logging.getLogger(override.name).setLevel(override.level)
    except ImportError:
        pass  # don't have redis
    except Exception:  # noqa: BLE001
        # survive an error there. Logging levels is not business critical...
        _LOGGER.warning("Cannot restore logging levels", exc_info=True)


async def startup(main_app: FastAPI) -> None:
    """Initialize application on startup."""
    del main_app  # Unused parameter
    global _set_level  # noqa: PLW0603
    _set_level = await broadcast.decorate(__set_level, expect_answers=True)
    await _restore_overrides()
    _LOGGER.info("Logging levels restored from Redis")


async def _store_override(name: str, level: str) -> None:
    try:
        master, _, _ = redis_utils.get()
        if master:
            await master.set(config.settings.tools.logging.redis_prefix + name, level)

    except ImportError:
        pass


async def _list_overrides() -> AsyncGenerator[OverrideResponse, None]:
    _, slave, _ = redis_utils.get()
    if slave is not None:
        async for key in slave.scan_iter(config.settings.tools.logging.redis_prefix + "*"):
            level = await slave.get(key)
            name = key[len(config.settings.tools.logging.redis_prefix) :]
            if level is not None:
                yield OverrideResponse(name=name, level=level)
