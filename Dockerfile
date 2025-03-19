FROM ubuntu:24.04 AS base-all

LABEL org.opencontainers.image.authors="Camptocamp <info@camptocamp.com>"

SHELL ["/bin/bash", "-o", "pipefail", "-cux"]

RUN --mount=type=cache,target=/var/lib/apt/lists \
    --mount=type=cache,target=/var/cache,sharing=locked \
    apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade --assume-yes \
    && DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get install --assume-yes --no-install-recommends tzdata \
    && DEBIAN_FRONTEND=noninteractive apt-get install --assume-yes --no-install-recommends python3-pip python3-venv \
    && python3 -m venv /venv

ENV PATH=/venv/bin:$PATH
ENV PYTHONPATH=/venv

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
    --mount=type=bind,from=poetry,source=/tmp,target=/poetry \
    python3 -m pip install --disable-pip-version-check --no-deps --requirement=/poetry/requirements.txt

WORKDIR /app

COPY c2casgiutils c2casgiutils
COPY pyproject.toml .

COPY requirements.txt README.md ./
RUN --mount=type=cache,target=/root/.cache \
    python3 -m pip install --disable-pip-version-check --requirement=requirements.txt \
    && poetry build --format=wheel

RUN --mount=type=cache,target=/root/.cache \
    --mount=type=bind,from=poetry,source=/tmp,target=/poetry \
    cp /poetry/requirements.txt .
