# {{cookiecutter.project_slug}}

{{cookiecutter.project_description}}

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- Python 3.10+

### Development

For local development with live reload, copy the sample override file:

```bash
cp docker-compose.override.sample.yaml docker-compose.override.yaml
```

Edit `docker-compose.override.yaml` to match your local environment, then start the application:

```bash
docker compose up --build --detach
```

## Project Structure

```
{{cookiecutter.project_slug}}/
├── {{cookiecutter.project_slug}}/  # Application source code
│   ├── __init__.py
│   ├── config.py         # Application environment variables (pydantic-settings)
│   ├── main.py           # FastAPI app with middleware and health checks
│   └── api.py            # API routes
├── Dockerfile            # Docker build
├── docker-compose.yaml   # Docker Compose configuration
├── docker-compose.override.sample.yaml  # Sample override for local dev
├── logging.yaml          # Logging configuration
├── pyproject.toml        # Project metadata and dependencies
```

## Configuration

### Application settings (`{{cookiecutter.project_slug|upper}}__` prefix)

Application-specific settings are defined in `{{cookiecutter.project_slug}}/config.py` using
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).
Variables use the prefix `{{cookiecutter.project_slug|upper}}__`, with `__` as the nested delimiter.

| Environment Variable | Description  | Default |
| ----------------------------------------------- | ----------------- | ------- |
| `{{cookiecutter.project_slug|upper}}\_\_DEBUG` | Enable debug mode | `False` |

Add your own settings by extending the `Settings` class in `config.py`:

```python
my_setting: Annotated[str, Field(description="My setting")] = "default"
```

Then set the environment variable `{{cookiecutter.project_slug|upper}}__MY_SETTING=value`.

### c2casgiutils settings (`C2C__` prefix)

The application is also configured via environment variables using the `C2C__` prefix.
See the [c2casgiutils documentation](https://github.com/camptocamp/c2casgiutils) for all available options.

| Environment Variable               | Description                       | Default                    |
| ---------------------------------- | --------------------------------- | -------------------------- |
| `C2C__REDIS__URL`                  | Redis connection URL              | `redis://localhost:6379/0` |
| `C2C__AUTH__JWT__SECRET`           | JWT secret key                    | _(required)_               |
| `C2C__AUTH__GITHUB__CLIENT_ID`     | GitHub OAuth client ID            | _(optional)_               |
| `C2C__AUTH__GITHUB__CLIENT_SECRET` | GitHub OAuth client secret        | _(optional)_               |
| `C2C__AUTH__GITHUB__REPOSITORY`    | GitHub repository for auth        | _(optional)_               |
| `C2C__HTTP`                        | Set to `True` to allow plain HTTP | `False`                    |
| `C2C__SENTRY__DSN`                 | Sentry DSN for error tracking     | _(optional)_               |

## Endpoints

| Path              | Description                             |
| ----------------- | --------------------------------------- |
| `GET /`           | Root endpoint returning a hello message |
| `GET /api/todo`   | Todo endpoint                           |
| `GET /c2c`        | c2casgiutils management UI              |
| `GET /c2c/health` | Health checks                           |

## Adding Features

### New API Endpoints

Add new routes to `{{cookiecutter.project_slug}}/api.py`:

```python
@app.get("/my-endpoint")
async def my_endpoint() -> MyResponse:
    """My endpoint description."""
    return MyResponse(...)
```

### Health Checks

Add custom health checks in `{{cookiecutter.project_slug}}/main.py`:

```python
health_checks.FACTORY.add(health_checks.Redis(tags=["liveness", "redis", "all"]))
```
