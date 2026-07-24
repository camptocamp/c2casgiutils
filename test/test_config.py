import datetime
import os

import pytest

from c2casgiutils.config import (
    Settings,
    parse_comma_separated_float_list,
    parse_comma_separated_int_list,
    parse_comma_separated_list,
    parse_duration,
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
