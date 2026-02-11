import os

import pytest

from c2casgiutils.config import Settings


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
