FROM ubuntu:24.04 AS base-all

LABEL org.opencontainers.image.authors="Camptocamp <info@camptocamp.com>"

SHELL ["/bin/bash", "-o", "pipefail", "-cux"]

RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache,sharing=locked \
    apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade --assume-yes \
    && DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get install --assume-yes --no-install-recommends tzdata \
    && DEBIAN_FRONTEND=noninteractive apt-get install --assume-yes --no-install-recommends python-is-python3 python3-venv \
    && python3 -m venv /venv

ENV PATH=/venv/bin:$PATH

# Used to convert the locked packages by poetry to pip requirements format
# We don't directly use `poetry install` because it force to use a virtual environment.
FROM base-all AS poetry

# Install Poetry
WORKDIR /tmp
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache \
    python3 -m pip install --disable-pip-version-check --requirement=requirements.txt

# Do the conversion
COPY poetry.lock pyproject.toml ./
RUN poetry export --output=requirements.txt

# Base, the biggest thing is to install the Python packages
FROM base-all AS base

RUN --mount=type=cache,target=/root/.cache \
    --mount=type=bind,from=c2casgiutils,source=/app,target=/c2casgiutils \
    --mount=type=bind,from=poetry,source=/tmp,target=/poetry \
    echo "Installing c2casgiutils" && \
    python3 -m pip install --disable-pip-version-check --no-deps --requirement=/c2casgiutils/requirements.txt && \
    python3 -m pip install --disable-pip-version-check --no-deps /c2casgiutils/dist/*.whl && \
    echo "Install fastapi_app dependencies" && \
    python3 -m pip install --disable-pip-version-check --no-deps --requirement=/poetry/requirements.txt

RUN python3 -m pip install --upgrade setuptools

WORKDIR /app

COPY fastapi_app fastapi_app
COPY pyproject.toml .

RUN --mount=type=cache,target=/root/.cache \
    python3 -m pip install --disable-pip-version-check --no-deps .

CMD ["uvicorn", "fastapi_app.main:app", "--host=0.0.0.0", "--port=8080"]
EXPOSE 8080
