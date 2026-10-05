.PHONY: help build build-frontend build-images up down test lint install clean meta-connect
.DEFAULT_GOAL := help

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"; printf "ArtistAssist targets:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  %-14s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install: ## Install backend + frontend dependencies
	@if [ -x backend/.venv/bin/python ]; then \
		backend/.venv/bin/python -m pip install -e "backend/[dev]"; \
	else \
		python3 -m pip install -e "backend/[dev]"; \
	fi
	cd frontend && npm install

build-frontend: ## Build frontend SPA to frontend/dist
	cd frontend && npm run build

build-images: ## Build Docker Compose images (project artistassist)
	docker compose -p artistassist build

build: ## Build frontend SPA and Docker images
	$(MAKE) build-frontend
	$(MAKE) build-images

up: ## Build frontend if needed, then start Compose stack
	@test -f .env || cp .env.example .env
	$(MAKE) build-frontend
	docker compose -p artistassist up -d --build

down: ## Stop Compose stack
	docker compose -p artistassist down

test: ## Run backend and frontend tests
	$(MAKE) -C backend test
	cd frontend && npm run test --if-present

lint: ## Lint backend and frontend
	$(MAKE) -C backend lint
	cd frontend && npm run lint

clean: ## Remove build artifacts
	rm -rf frontend/dist backend/.pytest_cache backend/.ruff_cache
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

WRITE_ENV ?= 1
# Comma-separated: all | facebook|fb,instagram|ig,threads
SERVICES ?= all

meta-connect: ## Connect Meta services via OAuth (SERVICES=all|fb,ig,threads)
	@test -f .env || cp .env.example .env
	@if [ -x backend/.venv/bin/python ]; then \
		PY=backend/.venv/bin/python; \
	elif command -v python3 >/dev/null 2>&1; then \
		PY=python3; \
	else \
		PY=python; \
	fi; \
	if [ "$(WRITE_ENV)" = "1" ]; then \
		$$PY backend/scripts/meta_token_bootstrap.py --write-env --services "$(SERVICES)"; \
	else \
		$$PY backend/scripts/meta_token_bootstrap.py --services "$(SERVICES)"; \
	fi
