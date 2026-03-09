# FastAPI Application Scaffold

A [Cookiecutter](https://cookiecutter.readthedocs.io/) template for bootstrapping a new FastAPI
application using `c2casgiutils`.

## Usage

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- [Cookiecutter](https://cookiecutter.readthedocs.io/): `pip install cookiecutter`

### Generate a new project

Run Cookiecutter, pointing it at this repository's `scaffold` directory:

```bash
cookiecutter https://github.com/camptocamp/c2casgiutils --directory scaffold
```

Or, if you have already cloned the repository locally:

```bash
cookiecutter path/to/c2casgiutils/scaffold
```

Cookiecutter will prompt for:

| Variable              | Description                                              | Default                                    |
| --------------------- | -------------------------------------------------------- | ------------------------------------------ |
| `project_slug`        | Python package / directory name (lowercase, underscores) | `my_project`                               |
| `project_description` | Short description added to `pyproject.toml`              | `A FastAPI application using c2casgiutils` |

The generated project is placed in a new directory named after `project_slug`.

### Start the application

```bash
cd <project_slug>
docker compose up --build
```

The application will be available at <http://localhost:8080>.

## Template structure

```
scaffold/
├── cookiecutter.json                     # Template variables and defaults
└── {{cookiecutter.project_slug}}/        # Project template
    ├── {{cookiecutter.project_slug}}/    # Application source code
    │   ├── __init__.py
    │   ├── main.py                       # FastAPI app with middleware and health checks
    │   └── api.py                        # API routes
    ├── Dockerfile                        # Docker build
    ├── docker-compose.yaml               # Docker Compose configuration
    ├── docker-compose.override.sample.yaml  # Sample override for local dev
    ├── logging.yaml                      # Logging configuration
    ├── pyproject.toml                    # Project metadata and dependencies
```
