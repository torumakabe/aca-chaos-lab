# Makefile for aca-chaos-lab

.PHONY: help
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: requirements
requirements: ## Generate requirements.txt from pyproject.toml
	uv pip compile pyproject.toml -o requirements.txt

.PHONY: install
install: ## Install development dependencies
	uv sync --all-extras

.PHONY: test
test: ## Run unit tests
	uv run pytest tests/unit/ -v -m unit

.PHONY: test-integration
test-integration: ## Run integration tests with Testcontainers
	./tests/run-integration-tests.sh

.PHONY: test-e2e
test-e2e: ## Run E2E tests against deployed environment
	./tests/e2e/run-e2e-tests.sh

.PHONY: test-load
test-load: ## Run load tests (baseline scenario)
	cd tests/load && ./run-load-tests.sh baseline

.PHONY: test-all
test-all: test test-integration ## Run unit and integration tests

.PHONY: lint
lint: ## Run linting
	uv run ruff check app/ --fix

.PHONY: typecheck
typecheck: ## Run type checking
	uv run mypy app/

.PHONY: format
format: ## Format code
	uv run ruff format app/

.PHONY: check
check: lint typecheck test ## Run all checks (lint, typecheck, test)

.PHONY: clean
clean: ## Clean up build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache

.PHONY: build
build: requirements ## Build Docker image locally
	docker build -t aca-chaos-lab:local .