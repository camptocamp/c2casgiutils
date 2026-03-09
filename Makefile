
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

.PHONY: poetry
poetry: pyproject.toml poetry.lock ## Install poetry dependencies
	poetry install --all-groups --all-extras

.PHONY: prospector
prospector: poetry ## Run prospector
	poetry run prospector --output-format=pylint

.PHONY: pytest
pytest: ## Run the unit pytest
	poetry run pytest test

.PHONY: settings-doc
settings-doc: poetry ## Run settings-doc
	poetry run settings-doc generate \
		--class=c2casgiutils.config.Settings \
		--output-format=markdown \
		--update=README.md \
		--between "<!-- generated env. vars. start -->" "<!-- generated env. vars. end -->" \
		--heading-offset=2
	sed --in-place --regexp "s#$(shell pwd)#<working_directory>#" README.md
	pre-commit run --color=never --files=README.md || true

.PHONY: acceptance_up
acceptance_up: build ## Start the fastapi application for acceptance tests
	(cd acceptance_tests/fastapi_app/ && docker compose build)
	(cd acceptance_tests/fastapi_app/ && docker compose up -d)

.PHONY: acceptance_poetry
acceptance_poetry: acceptance_tests/fastapi_app/pyproject.toml acceptance_tests/fastapi_app/poetry.lock ## Install poetry dependencies for fastapi application
	(cd acceptance_tests/fastapi_app/ && poetry install --all-groups --all-extras)
	(cd acceptance_tests/fastapi_app/ && poetry run pip install --editable=../..)

.PHONY: acceptance_prospector
acceptance_prospector: acceptance_poetry ## Run prospector for fastapi application
	(cd acceptance_tests/fastapi_app/ && poetry run prospector --output-format=pylint)

.PHONY: acceptance_pytest
acceptance_pytest: acceptance_up acceptance_poetry ## Run acceptance tests
	mkdir --parent acceptance_tests/fastapi_app/results/
	.github/wait-url http://localhost:8085
	(cd acceptance_tests/fastapi_app/ && poetry run pytest)

SCAFFOLD_OUTPUT := /tmp/c2casgiutils_scaffold_generated
SCAFFOLD_PROJECT := $(SCAFFOLD_OUTPUT)/my_project

.PHONY: scaffold_generate
scaffold_generate: scaffold/cookiecutter.json ## Generate scaffold project from cookiecutter template
	pip install --quiet cookiecutter
	cookiecutter --no-input scaffold/ --output-dir $(SCAFFOLD_OUTPUT)/ --overwrite-if-exists

.PHONY: scaffold_build
scaffold_build:  scaffold_generate  ## Build the scaffold application
	(cd $(SCAFFOLD_PROJECT) && docker compose build)
