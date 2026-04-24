The project must use async-friendly I/O APIs to avoid blocking the event loop.

- `pathlib` must not be used, use `anyio.Path` instead.
  Exceptions:
  - `c2casgiutils/scripts/*` are not concerned by this rule.
  - `pathlib.Path` can be used when opening files in a synchronous-only context where async is not possible.
- Converting a non-async function to `async` is allowed, and requires updating all call sites to `await` it.
- `aiofiles` must not be used, use `anyio.Path` instead.
- All disk or network operation must be done with async API; avoid blocking calls on the event loop.
- Don't allow sequential `await` calls in loops; use e.g. `asyncio.gather` or `asyncio.TaskGroup`.

## Environment variables

The environment variable should not be accessed directly (except the ones defined by another project); they should be defined in the `Settings` class in `c2casgiutils/config.py` and accessed through the `settings` object.

Exception:

- `SENTRY_DSN` can be accessed directly.

## Commit messages

The commit messages should be clear and descriptive, we don't use the conventional commits format,
the commit message should start with a capital letter.

## Bash

Use the long parameter names for clarity and maintainability.

## Development

To develop on the project, you should use the `acceptance_tests/fastapi_app/docker-compose.override.yaml` file.
Copy `acceptance_tests/fastapi_app/docker-compose.override.sample.yaml` to `acceptance_tests/fastapi_app/docker-compose.override.yaml`.

This will:

- Mount the local source code into the container.
- Enable the reload mode for the application.

To start the application, use the following command:

```bash
(cd acceptance_tests/fastapi_app/ && docker compose up -d)
```

The application will be available at:

- `http://localhost:8085/` for the application.
- `http://localhost:8086/` for the application with a test user.

## Scaffold

Ensure that scaffold in `scaffold/` is updated with the changes in the rest of the codebase.

Notes:

- the scaffold to be acceptable by everyone didn't uses Poetry to let the final user ti use other tools like `uv`.
- the scaffold is an empty application he has not the views with the broadcast like the application used in the
  acceptance tests.

## Documentation

The user documentation in the `README.md` file should be updated to reflect the changes in the codebase.

The changes in the codebase that affect the user or the developer that uses this library should be documented in the `CHANGELOG.md`.

## Tests

The new functionalities should be reasonably tested in the `test/` folder or `acceptance_tests/fastapi_app/test/` for acceptance tests.

The test files may not follow the rules concerning `async` requirements, as there are no performance requirements.

To run the tests, use the `make pytest` command or `make acceptance_pytest` respectively.

In the Docker container, the application is in the `/app` folder that directly contains the local files.

## Python Code Quality

To check the code quality, use the `make prospector` command.

- Ensure all Python code complies with:
  - Ruff rules configured for the project.
  - Formatter validations.
  - The oldest supported Python version (check `pyproject.toml`).
  - Use modern syntax.

## Changelog

The [changelog](./CHANGELOG.md) should respect the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) rules.
