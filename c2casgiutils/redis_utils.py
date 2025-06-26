import logging
from typing import Optional

import redis.asyncio.client
import redis.asyncio.sentinel
import redis.exceptions
import yaml

from c2casgiutils.config import settings

_LOG = logging.getLogger(__name__)


_master: Optional["redis.asyncio.client.Redis"] = None
_slave: Optional["redis.asyncio.client.Redis"] = None
_sentinel: redis.asyncio.sentinel.Sentinel | None = None


def cleanup() -> None:
    """Cleanup the redis connections."""
    global _master, _slave, _sentinel  # pylint: disable=global-statement
    _master = None
    _slave = None
    _sentinel = None


def get() -> tuple[
    Optional["redis.asyncio.client.Redis"],
    Optional["redis.asyncio.client.Redis"],
    redis.asyncio.sentinel.Sentinel | None,
]:
    """Get the redis connection instances."""
    if _master is None:
        _init()
    return _master, _slave, _sentinel


def _init() -> None:
    global _master, _slave, _sentinel  # pylint: disable=global-statement
    sentinels = settings.redis.sentinels
    url = settings.redis.url
    redis_options_ = settings.redis.options

    redis_options = (
        {}
        if redis_options_ is None
        else {
            e[0 : e.index("=")]: yaml.load(e[e.index("=") + 1 :], Loader=yaml.SafeLoader)
            for e in redis_options_.split(",")
        }
    )

    if sentinels:
        db = int(settings.redis.db)
        service_name = settings.redis.servicename
        if not service_name:
            message = "REDIS__SERVICENAME must be set when using Redis sentinels"
            raise ValueError(message)
        sentinels_str = [item.split(":") for item in sentinels.split(",")]
        _sentinel = redis.asyncio.sentinel.Sentinel(  # type: ignore[no-untyped-call]
            [(e[0], int(e[1])) for e in sentinels_str],
            decode_responses=True,
            db=db,
            **redis_options,
        )
        _LOG.info("Redis setup using: %s, %s, %s", sentinels, service_name, redis_options_)
        _master = _sentinel.master_for(service_name)
        _slave = _sentinel.slave_for(service_name)
        return
    if url:
        _LOG.info("Redis setup using: %s, with options: %s", url, redis_options_)
        _master = redis.asyncio.client.Redis.from_url(url, decode_responses=True, **redis_options)
        _slave = _master
    else:
        _LOG.info(
            "No Redis configuration found, use C2C__REDIS__URL or C2C__REDIS__SENTINELS settings to configure it",
        )
