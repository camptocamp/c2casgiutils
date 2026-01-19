import os

import pytest

from c2casgiutils.config import Settings


def test_tags_no_environment_variables():
    """Test tags field when no C2C__SENTRY__TAG_ environment variables are set."""
    # Save original environment
    original_env = os.environ.copy()
    
    try:
        # Clear any existing tag variables
        for key in list(os.environ.keys()):
            if key.startswith("C2C__SENTRY__TAG_"):
                del os.environ[key]
        
        # Create Settings which will initialize Sentry configuration
        settings = Settings()
        
        # Should have empty tags dict
        assert settings.sentry.tags == {}
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


def test_tags_single_environment_variable():
    """Test tags field with a single C2C__SENTRY__TAG_ environment variable."""
    # Save original environment
    original_env = os.environ.copy()
    
    try:
        # Clear any existing tag variables
        for key in list(os.environ.keys()):
            if key.startswith("C2C__SENTRY__TAG_"):
                del os.environ[key]
        
        # Set a single tag
        os.environ["C2C__SENTRY__TAG_ENVIRONMENT"] = "production"
        
        # Create Settings which will initialize Sentry configuration
        settings = Settings()
        
        # Should have one tag with lowercase key
        assert settings.sentry.tags == {"environment": "production"}
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


def test_tags_multiple_environment_variables():
    """Test tags field with multiple C2C__SENTRY__TAG_ environment variables."""
    # Save original environment
    original_env = os.environ.copy()
    
    try:
        # Clear any existing tag variables
        for key in list(os.environ.keys()):
            if key.startswith("C2C__SENTRY__TAG_"):
                del os.environ[key]
        
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
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


def test_tags_key_lowercased():
    """Test that tag keys are converted to lowercase."""
    # Save original environment
    original_env = os.environ.copy()
    
    try:
        # Clear any existing tag variables
        for key in list(os.environ.keys()):
            if key.startswith("C2C__SENTRY__TAG_"):
                del os.environ[key]
        
        # Set tags with uppercase keys
        os.environ["C2C__SENTRY__TAG_MYAPP"] = "value1"
        os.environ["C2C__SENTRY__TAG_SERVICE_NAME"] = "value2"
        
        # Create Settings which will initialize Sentry configuration
        settings = Settings()
        
        # Keys should be lowercase
        assert settings.sentry.tags == {
            "myapp": "value1",
            "service_name": "value2",
        }
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


def test_tags_only_correct_prefix():
    """Test that only environment variables with C2C__SENTRY__TAG_ prefix are parsed."""
    # Save original environment
    original_env = os.environ.copy()
    
    try:
        # Clear any existing tag variables
        for key in list(os.environ.keys()):
            if key.startswith("C2C__SENTRY__TAG_"):
                del os.environ[key]
        
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
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


def test_tags_with_special_characters():
    """Test tags with special characters in values."""
    # Save original environment
    original_env = os.environ.copy()
    
    try:
        # Clear any existing tag variables
        for key in list(os.environ.keys()):
            if key.startswith("C2C__SENTRY__TAG_"):
                del os.environ[key]
        
        # Set tags with special characters
        os.environ["C2C__SENTRY__TAG_PATH"] = "/var/log/app"
        os.environ["C2C__SENTRY__TAG_DESCRIPTION"] = "Test app with spaces"
        os.environ["C2C__SENTRY__TAG_SPECIAL"] = "value-with_special.chars"
        
        # Create Settings which will initialize Sentry configuration
        settings = Settings()
        
        # Should preserve special characters in values
        assert settings.sentry.tags == {
            "path": "/var/log/app",
            "description": "Test app with spaces",
            "special": "value-with_special.chars",
        }
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


def test_tags_with_empty_value():
    """Test tags with empty string values."""
    # Save original environment
    original_env = os.environ.copy()
    
    try:
        # Clear any existing tag variables
        for key in list(os.environ.keys()):
            if key.startswith("C2C__SENTRY__TAG_"):
                del os.environ[key]
        
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
    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)
