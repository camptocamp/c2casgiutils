# Camptocamp ASGI Utils

This package provides a set of utilities to help you build ASGI applications with Python.

## Stack

Stack that we consider that the project uses:

- [FastAPI](https://github.com/fastapi/fastapi)
- [uvicorn](https://www.uvicorn.org/)
- [SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Redis](https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html)
- [Prometheus FastAPI Instrumentator](https://github.com/trallnag/prometheus-fastapi-instrumentator)
- [Sentry](https://docs.sentry.io/platforms/python/integrations/fastapi/)
- [Pydantic settings](https://docs.pydantic.dev/latest/usage/settings/)

## Environment variables

See: https://github.com/camptocamp/c2casgiutils/blob/master/c2casgiutils/config.py

<!-- generated env. vars. start -->

### `C2C__REDIS__URL`

_Optional_, default value: `None`

Redis connection URL

### `C2C__REDIS__OPTIONS`

_Optional_, default value: `None`

Redis connection options, e.g. 'socket_timeout=5,ssl=True'.

### `C2C__REDIS__SENTINELS`

_Optional_, default value: `None`

Redis Sentinels

### `C2C__REDIS__SERVICENAME`

_Optional_, default value: `None`

Redis service name for Sentinel

### `C2C__REDIS__DB`

_Optional_, default value: `0`

Redis database number

### `C2C__REDIS__BROADCAST_PREFIX`

_Optional_, default value: `broadcast_api_`

Redis prefix for broadcast channels

### `C2C__PROMETHEUS__PREFIX`

_Optional_, default value: `c2casgiutils_`

Prefix for Prometheus metrics

### `C2C__PROMETHEUS__PORT`

_Optional_, default value: `9000`

Port for Prometheus metrics

### `C2C__SENTRY__DSN`

_Optional_, default value: `None`

Sentry DSN

### `C2C__SENTRY__DEBUG`

_Optional_, default value: `False`

Enable Sentry debug mode

### `C2C__SENTRY__RELEASE`

_Optional_, default value: `None`

Sentry release version

### `C2C__SENTRY__ENVIRONMENT`

_Optional_, default value: `production`

Sentry environment

### `C2C__SENTRY__DIST`

_Optional_, default value: `None`

Sentry distribution

### `C2C__SENTRY__SAMPLE_RATE`

_Optional_, default value: `1.0`

Sample rate for error events

### `C2C__SENTRY__IGNORE_ERRORS`

_Optional_, default value: `[]`

List of exception class names to ignore

### `C2C__SENTRY__MAX_BREADCRUMBS`

_Optional_, default value: `100`

Maximum number of breadcrumbs to capture

### `C2C__SENTRY__ATTACH_STACKTRACE`

_Optional_, default value: `False`

Attach stack trace to all messages

### `C2C__SENTRY__SEND_DEFAULT_PII`

_Optional_, default value: `None`

Send default PII

### `C2C__SENTRY__EVENT_SCRUBBER`

_Optional_, default value: `None`

Event scrubber for sensitive information

### `C2C__SENTRY__INCLUDE_SOURCE_CONTEXT`

_Optional_, default value: `True`

Include source context in events

### `C2C__SENTRY__INCLUDE_LOCAL_VARIABLES`

_Optional_, default value: `True`

Include local variables in events

### `C2C__SENTRY__ADD_FULL_STACK`

_Optional_, default value: `False`

Add full stack trace to events

### `C2C__SENTRY__MAX_STACK_FRAMES`

_Optional_, default value: `100`

Maximum number of stack frames to capture

### `C2C__SENTRY__SERVER_NAME`

_Optional_, default value: `None`

Server name for Sentry events

### `C2C__SENTRY__PROJECT_ROOT`

_Optional_, default value: `<working_directory>`

Root directory of the project

### `C2C__SENTRY__IN_APP_INCLUDE`

_Optional_, default value: `[]`

List of module prefixes that are in the app

### `C2C__SENTRY__IN_APP_EXCLUDE`

_Optional_, default value: `[]`

List of module prefixes that are not in the app

### `C2C__SENTRY__MAX_REQUEST_BODY_SIZE`

_Optional_, default value: `medium`

Maximum request body size to capture

### `C2C__SENTRY__MAX_VALUE_LENGTH`

_Optional_, default value: `1024`

Maximum length of values in event payloads

### `C2C__SENTRY__CA_CERTS`

_Optional_, default value: `None`

Path to alternative CA bundle file in PEM format

### `C2C__SENTRY__SEND_CLIENT_REPORTS`

_Optional_, default value: `True`

Send client reports to Sentry

### `C2C__AUTH__COOKIE_AGE`

_Optional_, default value: `604800`

Authentication cookie age in seconds (default: 7 days)

### `C2C__AUTH__COOKIE`

_Optional_, default value: `c2c-auth`

Authentication cookie name

### `C2C__AUTH__JWT__SECRET`

_Optional_, default value: `None`

JWT secret key

### `C2C__AUTH__JWT__ALGORITHM`

_Optional_, default value: `HS256`

JWT algorithm (default: HS256)

### `C2C__AUTH__JWT__COOKIE__SAME_SITE`

_Optional_, default value: `strict`

SameSite attribute for JWT cookie (default: strict)

#### Possible values

`lax`, `strict`, `none`

### `C2C__AUTH__JWT__COOKIE__SECURE`

_Optional_, default value: `True`

Whether the JWT cookie should be secure (default: True)

### `C2C__AUTH__JWT__COOKIE__PATH`

_Optional_, default value: `None`

Path for the JWT cookie (default: the path to the index page)

### `C2C__AUTH__SECRET`

_Optional_, default value: `None`

Secret key for trivial authentication (not secure)

### `C2C__AUTH__GITHUB__REPOSITORY`

_Optional_, default value: `None`

GitHub repository for authentication

### `C2C__AUTH__GITHUB__ACCESS_TYPE`

_Optional_, default value: `pull`

GitHub access type

### `C2C__AUTH__GITHUB__AUTHORIZE_URL`

_Optional_, default value: `https://github.com/login/oauth/authorize`

GitHub OAuth authorization URL

### `C2C__AUTH__GITHUB__TOKEN_URL`

_Optional_, default value: `https://github.com/login/oauth/access_token`

GitHub OAuth token URL

### `C2C__AUTH__GITHUB__USER_URL`

_Optional_, default value: `https://api.github.com/user`

GitHub user API URL

### `C2C__AUTH__GITHUB__REPO_URL`

_Optional_, default value: `https://api.github.com/repos`

GitHub repository API URL

### `C2C__AUTH__GITHUB__CLIENT_ID`

_Optional_, default value: `None`

GitHub OAuth client ID

### `C2C__AUTH__GITHUB__CLIENT_SECRET`

_Optional_, default value: `None`

GitHub OAuth client secret

### `C2C__AUTH__GITHUB__SCOPE`

_Optional_, default value: `repo`

GitHub OAuth scope

### `C2C__AUTH__GITHUB__PROXY_URL`

_Optional_, default value: `None`

GitHub proxy URL

### `C2C__AUTH__GITHUB__STATE_COOKIE`

_Optional_, default value: `c2c-state`

GitHub state cookie name

### `C2C__AUTH__GITHUB__STATE_COOKIE_AGE`

_Optional_, default value: `600`

GitHub state cookie age in seconds (default: 10 minutes)

### `C2C__AUTH__TEST__USERNAME`

_Optional_, default value: `None`

Test username

### `C2C__TOOLS__LOGGING__REDIS_PREFIX`

_Optional_, default value: `c2c_logging_level_`

Redis prefix for logging settings

### `C2C__TOOLS__LOGGING__APPLICATION_MODULE`

_Optional_, default value: `c2casgiutils`

Application module name for logging

<!-- generated env. vars. end -->

## Installation

```bash
pip install c2casgiutils[all]
```

Add in your application:

```python
import c2casgiutils
from c2casgiutils import broadcast
from c2casgiutils import config
from prometheus_client import start_http_server
from prometheus_fastapi_instrumentator import Instrumentator
from contextlib import asynccontextmanager

@asynccontextmanager
async def _lifespan(main_app: FastAPI) -> None:
    """Handle application lifespan events."""

    _LOGGER.info("Starting the application")
    await c2casgiutils.startup(main_app)

    yield

app = FastAPI(title="My fastapi_app application", lifespan=_lifespan)

app.mount('/c2c', c2casgiutils.app)

# For security headers (and compression)

# Add TrustedHostMiddleware (should be first)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],  # Configure with specific hosts in production
)

# Add HTTPSRedirectMiddleware
if os.environ.get("HTTP", "False").lower() not in ["true", "1"]:
    app.add_middleware(HTTPSRedirectMiddleware)

# Add GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Set all CORS origins enabled
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    headers.ArmorHeaderMiddleware,
    headers_config={
        "http": {"headers": {"Strict-Transport-Security": None} if http else {}},
    }
)

# Get Prometheus HTTP server port from environment variable 9000 by default
start_http_server(config.settings.prometheus.port)

instrumentator = Instrumentator(should_instrument_requests_inprogress=True)
instrumentator.instrument(app)
```

## Broadcasting

To use the broadcasting you should do something like this:

```python

import c2casgiutils
from typing import Protocol


class BroadcastResponse(BaseModel):
    """Response from broadcast endpoint."""

    result: list[dict[str, Any]] | None = None

class EchoHandlerProto(Protocol):
    async def __call__(self, *, message: str) -> list[dict[str, Any]] | None: ...


echo_handler: EchoHandlerProto = None  # type: ignore[assignment]

# Create a handler that will receive broadcasts
async def _echo_handler(*, message: str) -> dict[str, Any]:
    """Echo handler for broadcast messages."""
    return {"message": "Broadcast echo: " + message}

# Subscribe the handler to a channel on module import
@asynccontextmanager
async def _lifespan(main_app: FastAPI) -> None:
    """Handle application lifespan events."""

    _LOGGER.info("Starting the application")
    await c2casgiutils.startup(main_app)

    # Register the echo handler
    global echo_handler  # pylint: disable=global-statement
    echo_handler = await broadcast.decorate(_echo_handler, expect_answers=True)

    yield
```

Then you can use the `echo_handler` function you will have the response of all the registered applications.

## Health checks

The `health_checks` module provides a flexible system for checking the health of various components of your application. Health checks are exposed through a REST API endpoint at `/c2c/health_checks` and are also integrated with Prometheus metrics.

### Basic Usage

To initialize health checks in your application:

```python
from c2casgiutils import health_checks

# Add Redis health check
health_checks.FACTORY.add(health_checks.Redis(tags=["liveness", "redis", "all"]))

# Add SQLAlchemy database connection check
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
health_checks.FACTORY.add(health_checks.SQLAlchemy(Session=your_async_sessionmaker, tags=["database", "all"]))

# Add Alembic migration version check
health_checks.FACTORY.add(health_checks.Alembic(
    Session=your_async_sessionmaker,
    config_file="alembic.ini",
    tags=["migrations", "database", "all"]
))
```

### Available Health Checks

The package provides several built-in health check implementations:

1. **Redis**: Checks connectivity to Redis by pinging both master and slave instances
2. **SQLAlchemy**: Verifies database connectivity by executing a simple query
3. **Alembic**: Ensures the database schema is up-to-date with the latest migrations

### Custom Health Checks

You can create custom health checks by extending the `Check` base class:

```python
from c2casgiutils.health_checks import Check, Result

class MyCustomCheck(Check):
    async def check(self) -> Result:
        # Your check logic here
        try:
            # Perform your check...
            return Result(status_code=200, payload={"message": "Everything is fine!"})
        except Exception as e:
            return Result(status_code=500, payload={"error": str(e)})

# Add your custom check
health_checks.FACTORY.add(MyCustomCheck(tags=["custom", "all"]))
```

### Filtering Health Checks

Health checks can be filtered using tags or names:

- **Tags**: Add relevant tags when creating a check to categorize it
- **API Filtering**: Use query parameters to filter checks when calling the API:
  - `/c2c/health_checks?tags=database,critical` - Run only checks with "database" or "critical" tags
  - `/c2c/health_checks?name=Redis` - Run only the Redis check

### Prometheus Integration

Health check results are automatically exported to Prometheus metrics via the `health_checks_failure` gauge, allowing you to monitor and alert on health check failures.

## Middleware

### Headers Middleware

The `ArmorHeaderMiddleware` provides automatic security headers configuration for your ASGI application. It allows you to configure headers based on request netloc (host:port) and path patterns.

#### Basic Usage

```python
from c2casgiutils.headers import ArmorHeaderMiddleware

# Use default security headers
app.add_middleware(ArmorHeaderMiddleware)

# Or with custom configuration
app.add_middleware(ArmorHeaderMiddleware, headers_config=your_custom_config)
```

#### Default Security Headers

The middleware comes with sensible security defaults including:

- **Content-Security-Policy**: Restricts resource loading to prevent XSS attacks
- **X-Frame-Options**: Prevents clickjacking by denying iframe embedding
- **Strict-Transport-Security**: Forces HTTPS connections (disabled for localhost)
- **X-Content-Type-Options**: Prevents MIME-type sniffing
- **Referrer-Policy**: Controls referrer information sent with requests
- **Permissions-Policy**: Restricts access to browser features like geolocation
- **X-DNS-Prefetch-Control**: Disables DNS prefetching
- **Expect-CT**: Certificate Transparency enforcement
- **Origin-Agent-Cluster**: Isolates origin agent clusters
- **Cross-Origin policies**: CORP, COOP, COEP for cross-origin protection

#### Custom Configuration

You can configure headers based on request patterns:

```python
from c2casgiutils.headers import ArmorHeaderMiddleware

custom_config = {
    "api_endpoints": {
        "path_match": r"^/api/.*",  # Regex pattern for paths
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "X-Custom-Header": "api-value"
        },
        "order": 1  # Processing order
    },
    "admin_section": {
        "netloc_match": r"^admin\..*",  # Regex for host matching
        "path_match": r"^/admin/.*",
        "headers": {
            "X-Robots-Tag": "noindex, nofollow"
        },
        "status_code": 200,  # Only apply for specific status code
        "order": 2
    },
    "success_responses": {
        "headers": {
            "Cache-Control": ["public", "max-age=3600"]
        },
        "status_code": (200, 299),  # Apply for a range of status codes (200-299)
        "order": 3
    },
    "api_methods": {
        "path_match": r"^/api/.*",
        "methods": ["GET", "HEAD"],  # Only apply for specific HTTP methods
        "headers": {
            "Cache-Control": ["public", "max-age=3600"]
        },
        "order": 4
    },
    "remove_header": {
        "headers": {
            "Server": None  # Remove header by setting to None
        }
    }
}

app.add_middleware(ArmorHeaderMiddleware, headers_config=custom_config)
```

#### Header Value Types

Headers support multiple value types:

```python
headers = {
    # String value
    "X-Custom": "value",

    # List (joined with "; ")
    "Cache-Control": ["no-cache", "no-store", "must-revalidate"],

    # Dictionary (for complex headers like CSP)
    "Content-Security-Policy": {
        "default-src": ["'self'"],
        "script-src": ["'self'", "https://cdn.example.com"],
        "style-src": ["'self'", "'unsafe-inline'"]
    },

    # List (joined with ", ") for Permissions-Policy
    "Permissions-Policy": ["geolocation=()", "microphone=()"],

    # Remove header
    "Unwanted-Header": None
}
```

#### Special Localhost Handling

The middleware automatically disables `Strict-Transport-Security` for localhost to facilitate development.

#### Status Code Configuration

You can apply headers conditionally based on response status codes:

- Apply to a single status code: `"status_code": 200`
- Apply to a range of status codes: `"status_code": (200, 299)` (for all 2xx success responses)

This feature is useful for adding caching headers only to successful responses, or special headers for specific error codes.

#### HTTP Method Filtering

You can configure headers to be applied only for specific HTTP methods:

```python
{
    "api_post_endpoints": {
        "path_match": r"^/api/.*",
        "methods": ["POST", "PUT", "PATCH"],  # Only apply for these methods
        "headers": {
            "Cache-Control": "no-store"
        }
    },
    "api_get_endpoints": {
        "path_match": r"^/api/.*",
        "methods": ["GET", "HEAD"],  # Only apply for GET and HEAD requests
        "headers": {
            "Cache-Control": ["public", "max-age=3600"]
        }
    }
}
```

This allows for fine-grained control over which headers are applied based on the request method, useful for implementing different caching strategies for read vs. write operations.

#### Content-Security-Policy and security considerations

With the default CSP your html application will not work, to make it working without impacting the security Of the other pages you should add in the `headers_config` something like this:

```python
{
    "my_page": {
        "path_match": r"^your-path/?",
        "headers": {
            "Content-Security-Policy": {
                "default-src": ["'self'"],
                "script-src-elem": ["'self'", ...],
                "style-src-elem": ["'self'", ...],
            }
        },
        "order": 1
    }
}
```

And do the same for other headers.

#### Cache-Control Header

The `Cache-Control` header can be configured to control caching behavior for different endpoints. You can specify it as a string, list, or dictionary:

```python
{
    "api_endpoints": {
        "path_match": r"^/api/.*",
        "headers": {
            "Cache-Control": ["public", "max-age=3600"]  # Cache for 1 hour
        },
        "order": 1
    }
}
```

By default the middleware will not set any `Cache-Control` header, so you should explicitly configure it to enable caching.

## Authentication

The package also provides authentication utilities for GitHub-based authentication and API key validation. See the `auth.py` module for detailed configuration options.

## Prometheus Metrics

To enable Prometheus metrics in your FastAPI application, you can use the `prometheus_fastapi_instrumentator` package. Here's how to set it up:

```python
from c2casgiutils import config
from prometheus_client import start_http_server
from prometheus_fastapi_instrumentator import Instrumentator

# Get Prometheus HTTP server port from environment variable 9000 by default
start_http_server(config.settings.prometheus.port)

instrumentator = Instrumentator(should_instrument_requests_inprogress=True)
instrumentator.instrument(app)
```

## Sentry Integration

To enable error tracking with Sentry in your application:

```python
import os
import sentry_sdk

# Initialize Sentry if the URL is provided
if config.settings.sentry.dsn or 'SENTRY_DSN' in os.environ:
    _LOGGER.info("Sentry is enabled with URL: %s", config.settings.sentry.url or os.environ.get("SENTRY_DSN"))
    sentry_sdk.init(**config.settings.sentry.model_dump())
```

Sentry will automatically capture exceptions and errors in your FastAPI application. For more advanced usage, refer to the [Sentry Python SDK documentation](https://docs.sentry.io/platforms/python/) and [FastAPI integration guide](https://docs.sentry.io/platforms/python/integrations/fastapi/).
