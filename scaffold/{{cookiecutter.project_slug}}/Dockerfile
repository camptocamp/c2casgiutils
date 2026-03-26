FROM ubuntu:24.04

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

WORKDIR /app

COPY {{cookiecutter.project_slug}} {{cookiecutter.project_slug}}
COPY pyproject.toml logging.yaml ./

RUN --mount=type=cache,target=/root/.cache \
    python3 -m pip install --disable-pip-version-check .

CMD ["uvicorn", "{{cookiecutter.project_slug}}.main:app", "--host=0.0.0.0", "--port=8080", "--log-config=/app/logging.yaml", "--proxy-headers", "--forwarded-allow-ips=*"]

EXPOSE 8080
