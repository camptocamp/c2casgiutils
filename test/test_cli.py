import argparse
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from c2casgiutils import cli


@pytest.mark.asyncio
async def test_init_with_valid_logging_config():
    """Test init successfully loads and applies logging configuration."""
    # Create a temporary logging config file
    logging_config = {
        "version": 1,
        "formatters": {"simple": {"format": "%(levelname)s - %(message)s"}},
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
        "root": {"level": "INFO", "handlers": ["console"]},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp_file:
        yaml.dump(logging_config, tmp_file)
        tmp_path = tmp_file.name

    try:
        args = argparse.Namespace(logging_config=tmp_path)

        with (
            patch("c2casgiutils.config.settings") as mock_settings,
            patch("c2casgiutils.broadcast.startup") as mock_broadcast_startup,
            patch("c2casgiutils.cli.logging_tools.startup") as mock_logging_startup,
            patch("logging.config.dictConfig") as mock_dict_config,
        ):
            mock_settings.prometheus.port = None

            await cli.init(args)

            # Verify logging config was applied
            mock_dict_config.assert_called_once()
            called_config = mock_dict_config.call_args[0][0]
            assert called_config["version"] == 1
            assert "formatters" in called_config

            # Verify broadcast and logging startup were called
            mock_broadcast_startup.assert_called_once()
            mock_logging_startup.assert_called_once()
    finally:
        Path(tmp_path).unlink()


@pytest.mark.asyncio
async def test_init_with_none_logging_config():
    """Test init works when logging_config is None."""
    args = argparse.Namespace(logging_config=None)

    with (
        patch("c2casgiutils.config.settings") as mock_settings,
        patch("c2casgiutils.broadcast.startup") as mock_broadcast_startup,
        patch("c2casgiutils.cli.logging_tools.startup") as mock_logging_startup,
        patch("logging.config.dictConfig") as mock_dict_config,
    ):
        mock_settings.prometheus.port = None

        await cli.init(args)

        # Verify logging config was NOT applied (config is None)
        mock_dict_config.assert_not_called()

        # Verify broadcast and logging startup were called
        mock_broadcast_startup.assert_called_once()
        mock_logging_startup.assert_called_once()


@pytest.mark.asyncio
async def test_init_does_not_start_prometheus_when_not_configured():
    """Test init does not start Prometheus server when port is None."""
    args = argparse.Namespace(logging_config=None)

    with (
        patch("c2casgiutils.config.settings") as mock_settings,
        patch("c2casgiutils.broadcast.startup") as mock_broadcast_startup,
        patch("c2casgiutils.cli.logging_tools.startup") as mock_logging_startup,
        patch("prometheus_client.start_http_server") as mock_prometheus_start,
    ):
        mock_settings.prometheus.port = None

        await cli.init(args)

        # Verify Prometheus server was NOT started
        mock_prometheus_start.assert_not_called()

        # Verify broadcast and logging startup were called
        mock_broadcast_startup.assert_called_once()
        mock_logging_startup.assert_called_once()


@pytest.mark.asyncio
async def test_init_broadcast_integration():
    """Test init properly integrates with broadcast module."""
    args = argparse.Namespace(logging_config=None)

    with (
        patch("c2casgiutils.config.settings") as mock_settings,
        patch("c2casgiutils.broadcast.startup", new_callable=AsyncMock) as mock_broadcast_startup,
        patch("c2casgiutils.cli.logging_tools.startup"),
    ):
        mock_settings.prometheus.port = None

        await cli.init(args)

        # Verify broadcast.startup was called
        mock_broadcast_startup.assert_called_once_with()


@pytest.mark.asyncio
async def test_init_logging_integration():
    """Test init properly integrates with logging module."""
    args = argparse.Namespace(logging_config=None)

    with (
        patch("c2casgiutils.config.settings") as mock_settings,
        patch("c2casgiutils.broadcast.startup"),
        patch("c2casgiutils.cli.logging_tools.startup", new_callable=AsyncMock) as mock_logging_startup,
    ):
        mock_settings.prometheus.port = None

        await cli.init(args)

        # Verify logging.startup was called
        mock_logging_startup.assert_called_once_with()


@pytest.mark.asyncio
async def test_init_full_integration():
    """Test init with all features enabled."""
    # Create a valid logging config
    logging_config = {"version": 1, "root": {"level": "DEBUG"}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as tmp_file:
        yaml.dump(logging_config, tmp_file)
        tmp_path = tmp_file.name

    try:
        args = argparse.Namespace(logging_config=tmp_path)

        with (
            patch("c2casgiutils.config.settings") as mock_settings,
            patch("c2casgiutils.broadcast.startup") as mock_broadcast_startup,
            patch("c2casgiutils.cli.logging_tools.startup") as mock_logging_startup,
            patch("logging.config.dictConfig") as mock_dict_config,
        ):
            mock_settings.prometheus.port = 9090

            await cli.init(args)

            # Verify all components were initialized
            mock_dict_config.assert_called_once()
            mock_broadcast_startup.assert_called_once()
            mock_logging_startup.assert_called_once()
    finally:
        Path(tmp_path).unlink()
