.DEFAULT_GOAL := help
.PHONY: help install lint format test check ingest

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

install: ## Install dependencies from the lock file
	uv sync --locked

lint: ## Check lint and formatting (no changes)
	uv run ruff check .
	uv run ruff format --check .

format: ## Auto-format and apply safe lint fixes
	uv run ruff format .
	uv run ruff check --fix .

test: ## Run the tests
	uv run pytest

check: lint test ## Run lint and tests (same as CI)

FEEDS ?= station_status

ingest: ## Fetch feeds into data/ (FEEDS=station_status,station_information)
	uv run python -m ingestion --feeds $(FEEDS)
