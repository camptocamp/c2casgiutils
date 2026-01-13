# Inspired by fastapi_healthcheck

import asyncio
import logging
import time
from abc import abstractmethod
from typing import TYPE_CHECKING, Annotated, Any, cast

import prometheus_client
from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field

from c2casgiutils import config, redis_utils

if TYPE_CHECKING:
    import sqlalchemy.ext.asyncio

_LOGGER = logging.getLogger(__name__)

_PROMETHEUS_HEALTH_CHECKS_FAILURE = prometheus_client.Gauge(
    config.settings.prometheus.prefix + "health_checks_failure",
    "The health check",
    ["name"],
)


router = APIRouter()


class EntityResult(BaseModel):
    """
    Result of a single health check entity.
    """

    name: str
    tags: list[str]
    status_code: int = 200
    payload: dict[str, Any] = Field(default_factory=dict)
    time_taken: float = 0.0


class GlobalResult(BaseModel):
    """
    Global result of the health check.
    """

    status_code: int = 200
    time_taken: float = 0.0
    entities: list[EntityResult] = Field(default_factory=list)


class Result(BaseModel):
    """
    Result of a health check.
    """

    status_code: int = 200
    payload: dict[str, Any] = {}


class Check:
    """
    Base class for health checks.
    """

    def __init__(self, tags: list[str] | None = None) -> None:
        """
        Initialize the health check.
        """
        self._tags = tags or []

    @property
    def tags(self) -> list[str]:
        """
        Get the tags of the check.

        Tags can be used to filter checks in the health report.
        """
        return self._tags

    @property
    def name(self) -> str:
        """
        Get the name of the check.

        It is used to identify the check in the health report.
        """
        return self.__class__.__name__

    @abstractmethod
    async def check(self) -> Result:
        """
        Perform the health check and return a status code.

        The status code should be 200 for healthy, 500 for unhealthy.
        """


class Factory:
    """
    Factory for creating health checks.

    It allows adding multiple checks and running them all at once.
    It will return a GlobalResult object containing the results of all checks.
    """

    _items: list[Check]

    def __init__(self) -> None:
        self._items = []

    def add(self, item: Check) -> None:
        """
        Add a check item to the factory.
        """
        self._items.append(item)

    async def check(self, name: str | None, tags: str | None) -> GlobalResult:
        """
        Run all the checks in the factory concurrently and return a GlobalResult.

        It will create a GlobalResult object, run all checks concurrently,
        and collect their results.
        Each item's result will be added to the GlobalResult's entities list.
        The GlobalResult will also track the overall status code and time taken for all checks.
        """
        global_result = GlobalResult()
        global_start = time.perf_counter()

        async def run_single_check(item: Check) -> EntityResult:
            """Run a single check and return its EntityResult."""
            result = EntityResult(name=item.name, tags=item.tags)
            start = time.perf_counter()
            try:
                item_result = await item.check()
                result.status_code = item_result.status_code
                result.payload = item_result.payload
            except Exception as e:  # pylint: disable=broad-exception-caught
                _LOGGER.exception("Health check '%s' failed with exception", item.name)
                result.status_code = 500
                result.payload = {"error": str(e)}
            finally:
                end = time.perf_counter()
                result.time_taken = end - start

            _PROMETHEUS_HEALTH_CHECKS_FAILURE.labels(name=item.name).set(result.status_code)
            return result

        run_items = self._items
        if name:
            run_items = [item for item in run_items if item.name == name]
        if tags:
            tags_split = tags.split(",")
            run_items = [item for item in run_items if any(tag in item.tags for tag in tags_split)]

        # Run all checks concurrently
        if run_items:
            entity_results = await asyncio.gather(
                *[run_single_check(item) for item in run_items],
                return_exceptions=False,
            )

            # Collect results and determine global status
            for entity_result in entity_results:
                global_result.status_code = max(global_result.status_code, entity_result.status_code)
                global_result.entities.append(entity_result)  # pylint: disable=no-member

        global_end = time.perf_counter()
        global_result.time_taken = global_end - global_start

        return global_result


FACTORY = Factory()


@router.get("/")
async def c2c_health_checks(
    response: Response,
    name: Annotated[str | None, Query(description="Name of the check to run")] = None,
    tags: Annotated[str | None, Query(description="Comma-separated tags to filter checks")] = None,
) -> GlobalResult:
    """
    Health check endpoint.

    This endpoint will run all checks in the factory and return a GlobalResult.
    It can be filtered by name or tags using query parameters.
    """
    result = await FACTORY.check(name, tags)
    response.status_code = result.status_code
    return result


class Redis(Check):
    """
    Check the Redis connection.

    This check will ping both master and slave Redis instances if available.
    If both are the same instance, it will only ping once.
    """

    async def check(self) -> Result:
        """
        Check the Redis connection.

        This check will ping both master and slave Redis instances if available.
        If both are the same instance, it will only ping once.
        """
        master, slave, _ = redis_utils.get()
        payload = {}
        status_code = 200

        if master == slave:
            if master is not None:
                try:
                    await master.ping()  # type: ignore[misc]
                except Exception as e:  # pylint: disable=broad-exception-caught
                    _LOGGER.exception("Redis ping failed")
                    payload["error"] = str(e)
                    status_code = 500
        else:
            if master is not None:
                try:
                    await master.ping()  # type: ignore[misc]
                except Exception as e:  # pylint: disable=broad-exception-caught
                    _LOGGER.exception("Redis master ping failed")
                    payload["master_error"] = str(e)
                    status_code = 500
            if slave is not None:
                try:
                    await slave.ping()  # type: ignore[misc]
                except Exception as e:  # pylint: disable=broad-exception-caught
                    _LOGGER.exception("Redis slave ping failed")
                    payload["slave_error"] = str(e)
                    status_code = 500

        return Result(status_code=status_code, payload=payload)


class SQLAlchemy(Check):
    """
    Check the SQLAlchemy connection.

    This check will execute a simple query to verify the connection.
    """

    def __init__(
        self,
        Session: "sqlalchemy.ext.asyncio.async_sessionmaker[sqlalchemy.ext.asyncio.AsyncSession]",  # noqa: N803
        tags: list[str] | None = None,
    ) -> None:
        """
        Initialize the SQLAlchemy check with a connection string.
        """
        super().__init__(tags)
        self.Session = Session  # pylint: disable=invalid-name

    async def check(self) -> Result:
        """
        Check the SQLAlchemy connection.

        This check will execute a simple query to verify the connection.
        If the query fails, it will return a 500 status code with the error message.
        """
        import sqlalchemy  # noqa: PLC0415 # pylint: disable=import-outside-toplevel,import-error

        try:
            async with self.Session() as session:
                await session.execute(sqlalchemy.text("SELECT 1"))
        except Exception as e:  # pylint:disable=broad-exception-caught
            _LOGGER.exception("SQLAlchemy check failed")
            return Result(status_code=500, payload={"error": str(e)})

        return Result()


def _get_database_version(connection: "sqlalchemy.Connection") -> str | None:
    import alembic.runtime  # noqa: PLC0415 # pylint: disable=import-outside-toplevel,import-error

    context = alembic.runtime.migration.MigrationContext.configure(connection)
    return cast("str", context.get_current_revision())


class Alembic(Check):
    """
    Check the database version using Alembic.

    This check will compare the current database version with the head version
    defined in the Alembic script directory.
    """

    def __init__(
        self,
        Session: "sqlalchemy.ext.asyncio.async_sessionmaker[sqlalchemy.ext.asyncio.AsyncSession]",  # noqa: N803
        config_file: str = "alembic.ini",
        tags: list[str] | None = None,
    ) -> None:
        """
        Initialize the Alembic check with a configuration file.
        """
        super().__init__(tags)
        self.config_file = config_file
        self.Session = Session  # pylint: disable=invalid-name

    async def check(self) -> Result:
        """
        Check the database version using Alembic.
        """
        import alembic.config  # noqa: PLC0415 # pylint: disable=import-outside-toplevel,import-error
        import alembic.script  # noqa: PLC0415 # pylint: disable=import-outside-toplevel,import-error

        script = alembic.script.ScriptDirectory.from_config(alembic.config.Config(self.config_file))
        async with self.Session() as session:
            connection = await session.connection()
            current = await connection.run_sync(_get_database_version)
            head = script.get_current_head()
            if current != head:
                _LOGGER.error("Database is not up to date: current=%s, head=%s", current, head)
                return Result(
                    status_code=500,
                    payload={
                        "error": "Database is not up to date",
                        "current": current,
                        "head": head,
                    },
                )
            return Result(payload={"version": current, "head": head})


class Wrong(Check):
    """
    A check that always fails with a 500 status code.

    This is used for testing purposes to ensure the health check system can handle failures.
    """

    async def check(self) -> Result:
        """
        Check will always fail with a 500 status code.
        """
        return Result(
            status_code=500,
            payload={
                "error": "This is an always-failing check for testing purposes",
            },
        )
