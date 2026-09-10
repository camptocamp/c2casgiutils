# Copyright (c) 2025-2026, Camptocamp SA
import datetime
import os
import pathlib
from typing import Annotated

import anyio
import pytest
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from c2casgiutils.config import (
    Path,
    Settings,
    SiUnit,
    SiUnitInt,
    parse_comma_separated_float_list,
    parse_comma_separated_int_list,
    parse_comma_separated_list,
    parse_duration,
    parse_path,
    parse_si_unit,
    parse_si_unit_int,
)


def test_parse_duration_iso():
    assert parse_duration("PT1M") == datetime.timedelta(minutes=1)
    assert parse_duration("PT2M30S") == datetime.timedelta(minutes=2, seconds=30)
    assert parse_duration("PT1H") == datetime.timedelta(hours=1)
    assert parse_duration("P1D") == datetime.timedelta(days=1)


def test_parse_duration_short():
    assert parse_duration("10m") == datetime.timedelta(minutes=10)
    assert parse_duration("2h30") == datetime.timedelta(hours=2, minutes=30)
    assert parse_duration("1d") == datetime.timedelta(days=1)
    assert parse_duration("1w") == datetime.timedelta(weeks=1)
    assert parse_duration("1w2d3h4m5s") == datetime.timedelta(weeks=1, days=2, hours=3, minutes=4, seconds=5)


def test_parse_duration_plain_seconds():
    assert parse_duration("300") == datetime.timedelta(seconds=300)
    assert parse_duration("0") == datetime.timedelta(seconds=0)


def test_parse_duration_timedelta_passthrough():
    td = datetime.timedelta(minutes=5)
    assert parse_duration(td) is td


def test_parse_duration_invalid():
    with pytest.raises(ValueError, match="Invalid time delta"):
        parse_duration("not_a_duration")


@pytest.fixture
def clean_env():
    """Fixture to clean and restore environment variables."""
    # Save original environment
    original_env = os.environ.copy()

    # Clear any existing tag variables before test
    for key in list(os.environ.keys()):
        if key.startswith("C2C__SENTRY__TAG_"):
            del os.environ[key]

    yield

    # Restore original environment after test
    # Remove any tag variables that were added during the test
    for key in list(os.environ.keys()):
        if key.startswith("C2C__SENTRY__TAG_") and key not in original_env:
            del os.environ[key]
    # Restore original values
    for key, value in original_env.items():
        if key.startswith("C2C__SENTRY__TAG_"):
            os.environ[key] = value


def test_tags_no_environment_variables(clean_env):
    """Test tags field when no C2C__SENTRY__TAG_ environment variables are set."""
    # Create Settings which will initialize Sentry configuration
    settings = Settings()

    # Should have empty tags dict
    assert settings.sentry.tags == {}


def test_tags_single_environment_variable(clean_env):
    """Test tags field with a single C2C__SENTRY__TAG_ environment variable."""
    # Set a single tag
    os.environ["C2C__SENTRY__TAG_ENVIRONMENT"] = "production"

    # Create Settings which will initialize Sentry configuration
    settings = Settings()

    # Should have one tag with lowercase key
    assert settings.sentry.tags == {"environment": "production"}


def test_tags_multiple_environment_variables(clean_env):
    """Test tags field with multiple C2C__SENTRY__TAG_ environment variables."""
    # Set multiple tags
    os.environ["C2C__SENTRY__TAG_ENVIRONMENT"] = "production"
    os.environ["C2C__SENTRY__TAG_VERSION"] = "1.2.3"
    os.environ["C2C__SENTRY__TAG_REGION"] = "eu-west-1"

    # Create Settings which will initialize Sentry configuration
    settings = Settings()

    # Should have all tags with lowercase keys
    assert settings.sentry.tags == {
        "environment": "production",
        "version": "1.2.3",
        "region": "eu-west-1",
    }


def test_tags_only_correct_prefix(clean_env):
    """Test that only environment variables with C2C__SENTRY__TAG_ prefix are parsed."""
    # Set various environment variables
    os.environ["C2C__SENTRY__TAG_VALID"] = "included"
    os.environ["C2C__SENTRY__INVALID"] = "not_included"
    os.environ["SENTRY__TAG_INVALID"] = "not_included"
    os.environ["TAG_INVALID"] = "not_included"
    os.environ["RANDOM_VAR"] = "not_included"

    # Create Settings which will initialize Sentry configuration
    settings = Settings()

    # Should only have the valid tag
    assert settings.sentry.tags == {"valid": "included"}


def test_tags_with_empty_value(clean_env):
    """Test tags with empty string values."""
    # Set tag with empty value
    os.environ["C2C__SENTRY__TAG_EMPTY"] = ""
    os.environ["C2C__SENTRY__TAG_NONEMPTY"] = "value"

    # Create Settings which will initialize Sentry configuration
    settings = Settings()

    # Should include both tags
    assert settings.sentry.tags == {
        "empty": "",
        "nonempty": "value",
    }


def test_proxy_headers_defaults(clean_env):
    settings = Settings()

    assert settings.proxy_headers.type == "none"
    assert settings.proxy_headers.trusted_hosts == ["127.0.0.1"]


def test_proxy_headers_from_environment(clean_env):
    os.environ["C2C__PROXY_HEADERS__TYPE"] = "x-forwarded"
    os.environ["C2C__PROXY_HEADERS__TRUSTED_HOSTS"] = "127.0.0.1,10.0.0.0/8, 192.168.1.1"

    settings = Settings()

    assert settings.proxy_headers.type == "x-forwarded"
    assert settings.proxy_headers.trusted_hosts == ["127.0.0.1", "10.0.0.0/8", "192.168.1.1"]


def test_proxy_headers_forwarded_type(clean_env):
    os.environ["C2C__PROXY_HEADERS__TYPE"] = "forwarded"

    settings = Settings()

    assert settings.proxy_headers.type == "forwarded"


def test_auth_github_access_token_expiration_margin_from_environment(clean_env):
    os.environ["C2C__AUTH__GITHUB__ACCESS_TOKEN_EXPIRATION_MARGIN"] = "PT2M30S"

    settings = Settings()

    assert settings.auth.github.access_token_expiration_margin == datetime.timedelta(minutes=2, seconds=30)


def test_auth_github_access_token_expiration_margin_short_format(clean_env):
    os.environ["C2C__AUTH__GITHUB__ACCESS_TOKEN_EXPIRATION_MARGIN"] = "5m"

    settings = Settings()

    assert settings.auth.github.access_token_expiration_margin == datetime.timedelta(minutes=5)


def test_auth_github_access_token_expiration_margin_plain_seconds(clean_env):
    os.environ["C2C__AUTH__GITHUB__ACCESS_TOKEN_EXPIRATION_MARGIN"] = "120"

    settings = Settings()

    assert settings.auth.github.access_token_expiration_margin == datetime.timedelta(seconds=120)


def test_redis_options_none():
    settings = Settings()

    assert settings.redis.options == {}


def test_redis_options_from_environment(clean_env):
    os.environ["C2C__REDIS__OPTIONS"] = "socket_timeout=5,ssl=True"

    settings = Settings()

    assert settings.redis.options == {"socket_timeout": 5, "ssl": True}


def test_parse_comma_separated_list_none():
    assert parse_comma_separated_list(None) == []


def test_parse_comma_separated_list_list():
    assert parse_comma_separated_list(["a", "b"]) == ["a", "b"]


def test_parse_comma_separated_list_list_with_spaces():
    assert parse_comma_separated_list([" a ", " b "]) == ["a", "b"]


def test_parse_comma_separated_list_empty():
    assert parse_comma_separated_list("") == []


def test_parse_comma_separated_list_single():
    assert parse_comma_separated_list("value") == ["value"]


def test_parse_comma_separated_list_multiple():
    assert parse_comma_separated_list("a,b,c") == ["a", "b", "c"]


def test_parse_comma_separated_list_with_spaces():
    assert parse_comma_separated_list("a, b, c") == ["a", "b", "c"]


def test_sentry_ignore_errors_from_environment(clean_env):
    os.environ["C2C__SENTRY__IGNORE_ERRORS"] = "ValueError,TypeError,RuntimeError"
    settings = Settings()
    assert settings.sentry.ignore_errors == ["ValueError", "TypeError", "RuntimeError"]


def test_sentry_in_app_include_from_environment(clean_env):
    os.environ["C2C__SENTRY__IN_APP_INCLUDE"] = "myapp,myapp2"
    settings = Settings()
    assert settings.sentry.in_app_include == ["myapp", "myapp2"]


def test_sentry_in_app_exclude_from_environment(clean_env):
    os.environ["C2C__SENTRY__IN_APP_EXCLUDE"] = "test,test2"
    settings = Settings()
    assert settings.sentry.in_app_exclude == ["test", "test2"]


def test_proxy_headers_trusted_hosts_from_environment(clean_env):
    os.environ["C2C__PROXY_HEADERS__TRUSTED_HOSTS"] = "127.0.0.1,10.0.0.0/8, 192.168.1.1"
    settings = Settings()
    assert settings.proxy_headers.trusted_hosts == ["127.0.0.1", "10.0.0.0/8", "192.168.1.1"]


def test_parse_comma_separated_int_list():
    assert parse_comma_separated_int_list("1,2,3") == [1, 2, 3]
    assert parse_comma_separated_int_list("1, 2, 3") == [1, 2, 3]
    assert parse_comma_separated_int_list(None) == []
    assert parse_comma_separated_int_list([1, 2, 3]) == [1, 2, 3]


def test_parse_comma_separated_float_list():
    assert parse_comma_separated_float_list("1.5,2.5,3.5") == [1.5, 2.5, 3.5]
    assert parse_comma_separated_float_list("1.5, 2.5, 3.5") == [1.5, 2.5, 3.5]
    assert parse_comma_separated_float_list(None) == []
    assert parse_comma_separated_float_list([1.5, 2.5, 3.5]) == [1.5, 2.5, 3.5]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1", 1.0),
        ("1000", 1000.0),
        ("-1.5", -1.5),
        ("1Q", 1e30),
        ("1R", 1e27),
        ("1Y", 1e24),
        ("1Z", 1e21),
        ("1E", 1e18),
        ("1P", 1e15),
        ("1T", 1e12),
        ("1G", 1e9),
        ("1M", 1e6),
        ("1k", 1e3),
        ("1K", 1e3),
        ("1h", 1e2),
        ("1da", 1e1),
        ("1d", 1e-1),
        ("1c", 1e-2),
        ("1m", 1e-3),
        ("1\u00b5", 1e-6),
        ("1\u03bc", 1e-6),
        ("1u", 1e-6),
        ("1n", 1e-9),
        ("1p", 1e-12),
        ("1f", 1e-15),
        ("1a", 1e-18),
        ("1z", 1e-21),
        ("1y", 1e-24),
        ("1r", 1e-27),
        ("1q", 1e-30),
    ],
)
def test_parse_si_unit_decimal_prefixes(text, expected):
    assert parse_si_unit(text) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1Ki", 1024.0),
        ("1ki", 1024.0),
        ("1Mi", 1024.0**2),
        ("1Gi", 1024.0**3),
        ("1Ti", 1024.0**4),
        ("1Pi", 1024.0**5),
        ("1Ei", 1024.0**6),
        ("1Zi", 1024.0**7),
        ("1Yi", 1024.0**8),
    ],
)
def test_parse_si_unit_binary_prefixes(text, expected):
    assert parse_si_unit(text) == pytest.approx(expected)


def test_parse_si_unit_trailing_letter_ignored():
    assert parse_si_unit("1kB") == 1000.0
    assert parse_si_unit("1KiB") == 1024.0
    assert parse_si_unit("2Go") == 2e9
    assert parse_si_unit("500MiB") == 500 * 1024.0**2
    assert parse_si_unit("5cm") == 0.05
    assert parse_si_unit("3µs") == 3e-6


def test_parse_si_unit_fractional_and_spaces():
    assert parse_si_unit("1.5G") == 1.5e9
    assert parse_si_unit("1.5Ki") == 1536.0
    assert parse_si_unit("  10M  ") == 10e6
    assert parse_si_unit("-5M") == -5e6


def test_parse_si_unit_numeric_passthrough():
    assert parse_si_unit(1000) == 1000.0
    assert parse_si_unit(1.5) == 1.5
    assert parse_si_unit(-2) == -2.0


def test_parse_si_unit_case_sensitive():
    # `M` is mega and `m` is milli.
    assert parse_si_unit("10M") == 10e6
    assert parse_si_unit("10m") == 0.01


@pytest.mark.parametrize("text", ["not_a_size", "1i", "1xi", "1XY", "1.2.3", "M", "", "1 Q"])
def test_parse_si_unit_invalid(text):
    with pytest.raises(ValueError, match="Invalid"):
        parse_si_unit(text)


def test_parse_si_unit_int():
    assert parse_si_unit_int("10M") == 10_000_000
    assert parse_si_unit_int("500MiB") == 524_288_000
    assert parse_si_unit_int("3G") == 3_000_000_000
    assert parse_si_unit_int("1.5K") == 1500
    assert parse_si_unit_int(1024) == 1024
    # The int result is exact, not limited by the float precision.
    assert parse_si_unit_int("1Q") == 10**30
    assert parse_si_unit_int("1m") == 0


def test_parse_path_from_string():
    result = parse_path("/tmp/test")
    assert isinstance(result, anyio.Path)
    assert str(result) == "/tmp/test"


def test_parse_path_from_pathlib():
    result = parse_path(pathlib.Path("/tmp/test"))
    assert isinstance(result, anyio.Path)
    assert str(result) == "/tmp/test"


def test_parse_path_from_anyio():
    path = anyio.Path("/tmp/test")
    assert parse_path(path) is path


class _TypesModel(BaseModel):
    size: Annotated[SiUnit, Field(description="Size")]
    size_int: Annotated[SiUnitInt, Field(description="Size as int")]
    path: Annotated[Path, Field(description="Path")]


def test_types_model_validation():
    model = _TypesModel.model_validate({"size": "1.5G", "size_int": "500MiB", "path": "/tmp/test"})

    assert model.size == 1.5e9
    assert model.size_int == 524_288_000
    assert isinstance(model.path, anyio.Path)
    assert str(model.path) == "/tmp/test"


def test_types_model_serialization():
    model = _TypesModel(size=1024, size_int=1024, path=parse_path("/tmp/test"))

    assert model.model_dump() == {"size": 1024.0, "size_int": 1024, "path": "/tmp/test"}
    assert model.model_dump_json() == '{"size":1024.0,"size_int":1024,"path":"/tmp/test"}'
    json_schema = _TypesModel.model_json_schema()
    assert json_schema["properties"]["path"]["type"] == "string"


def test_types_model_invalid():
    with pytest.raises(ValueError, match="Invalid SI unit"):
        _TypesModel.model_validate({"size": "nope", "size_int": "1k", "path": "/tmp"})
    with pytest.raises(ValueError, match="Path"):
        _TypesModel.model_validate({"size": "1k", "size_int": "1k", "path": 42})


def test_types_path_default_is_not_validated():
    """Pydantic does not validate the defaults, they must be wrapped in `parse_path`."""

    class Model(BaseModel):
        raw: Annotated[Path, Field(description="Raw default")] = Field(default="/app/templates")
        parsed: Annotated[Path, Field(description="Parsed default")] = parse_path("/app/templates")

    model = Model()

    assert isinstance(model.raw, str)
    assert isinstance(model.parsed, anyio.Path)


class _TypesSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="C2C_TEST_TYPES__")

    size: Annotated[SiUnit, Field(description="Size")] = parse_si_unit("100M")
    size_int: Annotated[SiUnitInt, Field(description="Size as int")] = parse_si_unit_int("10M")
    path: Annotated[Path, Field(description="Path")] = parse_path("/app/templates")


def test_types_settings_defaults():
    settings = _TypesSettings()

    assert settings.size == 100e6
    assert settings.size_int == 10_000_000
    assert isinstance(settings.path, anyio.Path)
    assert str(settings.path) == "/app/templates"


def test_types_settings_from_environment(monkeypatch):
    monkeypatch.setenv("C2C_TEST_TYPES__SIZE", "2Gi")
    monkeypatch.setenv("C2C_TEST_TYPES__SIZE_INT", "500MiB")
    monkeypatch.setenv("C2C_TEST_TYPES__PATH", "/var/log/app.log")

    settings = _TypesSettings()

    assert settings.size == 2 * 1024.0**3
    assert settings.size_int == 524_288_000
    assert isinstance(settings.path, anyio.Path)
    assert str(settings.path) == "/var/log/app.log"
