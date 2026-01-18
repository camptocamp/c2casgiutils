import argparse
import logging
import logging.config

import aiofiles
import prometheus_client
import yaml

import c2casgiutils.config
from c2casgiutils import broadcast
from c2casgiutils.tools import logging_ as logging_tools

_LOGGER = logging.getLogger(__name__)


def all_arguments(
    arg_parser: argparse.ArgumentParser, default_logging_config: str | None = "logging.yaml"
) -> None:
    """Add all arguments for the command line application."""
    arg_parser.add_argument(
        "--logging-config",
        type=str,
        default=default_logging_config,
        help="Path to the logging configuration YAML file.",
    )


async def init(args: argparse.Namespace) -> None:
    """Initialize command line application."""

    if args.logging_config is not None:
        try:
            async with aiofiles.open(args.logging_config) as logging_file:
                logging_config = yaml.safe_load(await logging_file.read())
                logging.config.dictConfig(logging_config)
        except yaml.YAMLError:
            _LOGGER.exception("Failed to parse logging configuration file '%s'", args.logging_config)

    if c2casgiutils.config.settings.prometheus.port is not None:
        prometheus_client.start_http_server(c2casgiutils.config.settings.prometheus.port)

    await broadcast.startup()
    # If the command line application has also a FastAPI app, this will allow changing the logging levels from the FastAPI application
    await logging_tools.startup()
