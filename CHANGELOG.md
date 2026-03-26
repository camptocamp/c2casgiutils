# Changelog

## 0.8

### Added

- **Headers**: Added `HTTPSRedirectMiddleware` that redirects HTTP to HTTPS while bypassing requests from `localhost` (matching `^localhost(:\d+)?$`), allowing Kubernetes liveness/readiness probes to work over plain HTTP.

## 0.7

### ⚠️ Breaking Changes & Migration Guide

#### Application

Changes have been made to the example application structure and configuration. If you are maintaining an application based on this template, please apply the following changes:

1.  **Environment Variables (HTTP Mode)**:
    The management of HTTP mode (development) has been standardized.
    - **Change**: Replace the `HTTP` environment variable with `C2C__HTTP`.
    - **In `docker-compose.yaml`**:
      ```diff
      -      - HTTP=True
      +      - C2C__HTTP=True
      ```
    - **In the code (`main.py`)**: Use `config.settings.http` instead of reading `os.environ["HTTP"]`.

2.  **Sentry Configuration**:
    The `Sentry` configuration object now includes a `tags` field which must not be passed directly to `sentry_sdk.init()`.
    - **Action**: Update Sentry initialization to exclude tags from the `init` call and set them separately.
    - **Code (`main.py`)**:

    ```python
    if config.settings.sentry.dsn or "SENTRY_DSN" in os.environ:
        # ... logs ...
        # Filter out None values and 'tags' from the init call
        sentry_config = config.settings.sentry.model_dump()
        sentry_init_args = {k: v for k, v in sentry_config.items() if v is not None and k != "tags"}
        sentry_sdk.init(**sentry_init_args)

        # Set tags separately
        for tag, value in config.settings.sentry.tags.items():
            sentry_sdk.set_tag(tag, value)
    ```

3.  **Broadcast Handler**:
    **BREAKING CHANGE**: The `broadcast.decorate` function now enforces keyword-only arguments for the decorated function.
    - **Action**: Check all calls to functions wrapped via `await broadcast.decorate(...)` and ensure they use keyword arguments.
    - **Action**: Update handler signatures to enforce keyword arguments (recommended).
    - **Example (`api.py`)**:

    ```python
    # Update the handler signature
    async def __echo_handler(*, message: str) -> dict[str, Any]: # Add *,
        """Echo handler for broadcast messages."""
        return {"message": "Broadcast echo: " + message}

    _echo_handler = None

    async def startup(main_app: FastAPI) -> None:
        """Initialize application on startup."""
        del main_app  # Unused parameter, but required
        global _echo_handler
        _echo_handler = await broadcast.decorate(__echo_handler, expect_answers=True)

    # Call
    await _echo_handler(message="coucou") # Mandatory: _echo_handler("coucou") will no longer work
    ```

4.  **Middleware Configuration**:
    If you use `ArmorHeaderMiddleware`, update the condition based on HTTP mode.
    - **Code (`main.py`)**:

    ```python
    app.add_middleware(
        headers.ArmorHeaderMiddleware,
        headers_config={"http": {"headers": {"Strict-Transport-Security": None}}}
        if not config.settings.http # Use config settings
        else {},
    )
    ```

### Added

- **Headers**: Added support for `Content-Security-Policy` Nonce.
- **Headers**: Added support for `Content-Security-Policy-Report-Only` header.
- **Headers**: Can match on `Content-Type`.
- **Sentry**: Added support for Sentry tags in configuration.
- **CLI**: Added helper for command line applications.
- **Broadcast**: Allows broadcasting on non-async functions.
- **Broadcast**: Supports Pydantic models in parameters and results.
- **Auth**: Improved error handling when the JWT secret is not provided.

### Changed

- **Settings**: Added more environment variables to settings.
