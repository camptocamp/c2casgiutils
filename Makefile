
.PHONY: help
help: ## Display this help message
	@echo "Usage: make <target>"
	@echo
	@echo "Available targets:"
	@grep --extended-regexp --no-filename '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "	%-25s%s\n", $$1, $$2}'


.PHONY: build
build:  ## Build the c2casgiutils docker image
	docker build --tag=c2casgiutils .

poetry: pyproject.toml poetry.lock ## Install poetry dependencies
	poetry install --all-groups --all-extras

prospector: poetry ## Run prospector
	poetry run prospector --output-format=pylint

pytest: ## Run the unit pytest
	poetry run pytest test

acceptance_up: build ## Start the fastapi application for acceptance tests
	(cd acceptance_tests/fastapi_app/ && docker compose build)
	(cd acceptance_tests/fastapi_app/ && docker compose up -d)

acceptance_poetry: acceptance_tests/fastapi_app/pyproject.toml acceptance_tests/fastapi_app/poetry.lock ## Install poetry dependencies for fastapi application
	(cd acceptance_tests/fastapi_app/ && poetry install --all-groups --all-extras)
	(cd acceptance_tests/fastapi_app/ && poetry run pip install --editable=../..)

acceptance_prospector: acceptance_poetry ## Run prospector for fastapi application
	(cd acceptance_tests/fastapi_app/ && poetry run prospector --output-format=pylint)

acceptance_pytest: acceptance_up acceptance_poetry ## Run acceptance tests
	mkdir --parent acceptance_tests/fastapi_app/results/
	.github/wait-url http://localhost:8085
	(cd acceptance_tests/fastapi_app/ && poetry run pytest)
