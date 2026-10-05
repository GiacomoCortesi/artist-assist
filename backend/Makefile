.PHONY: help test lint run
.DEFAULT_GOAL := help

# Prefer local venv, then python3, then python
PYTHON := $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; \
	elif command -v python3 >/dev/null 2>&1; then command -v python3; \
	else command -v python; fi)

help: ## Show backend targets
	@awk 'BEGIN {FS = ":.*##"; printf "Backend targets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  %-12s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

test: ## Run backend unit tests
	$(PYTHON) -m pytest -q

lint: ## Lint backend with ruff
	$(PYTHON) -m ruff check app tests

run: ## Run API with uvicorn (dev)
	$(PYTHON) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
