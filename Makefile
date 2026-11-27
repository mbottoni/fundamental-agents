.PHONY: help up down build restart logs logs-backend logs-frontend logs-db \
       shell-backend shell-frontend shell-db \
       health test test-backend test-ci gen-types \
       clean clean-volumes reset \
       migrate migrate-create migrate-history migrate-check \
       prod-build prod-up prod-down prod-logs smoke \
       secret-key db-tables db-users db-jobs

# ══════════════════════════════════════════════════════════════
# Default
# ══════════════════════════════════════════════════════════════

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ══════════════════════════════════════════════════════════════
# Docker Compose (Development)
# ══════════════════════════════════════════════════════════════

up: ## Start all services (with build)
	docker-compose up --build

up-d: ## Start all services in background
	docker-compose up --build -d

down: ## Stop all services
	docker-compose down

build: ## Rebuild all images without cache
	docker-compose build --no-cache

restart: ## Restart all services
	docker-compose down && docker-compose up --build

restart-backend: ## Restart only the backend
	docker-compose restart backend

restart-frontend: ## Restart only the frontend
	docker-compose restart frontend

# ══════════════════════════════════════════════════════════════
# Production
# ══════════════════════════════════════════════════════════════

# The production stack on this machine, from images built here, at
# http://localhost:$(PROD_PORT). Needs a .env.prod (copy .env.prod.example)
# with SITE_ADDRESS=:80, so Caddy serves plain HTTP and asks for no
# certificate, and FRONTEND_URL=http://localhost:$(PROD_PORT).
PROD_PORT ?= 8080
PROD_COMPOSE = IMAGE_TAG=local HTTP_PORT=$(PROD_PORT) HTTPS_PORT=8443 \
	docker compose -f docker-compose.prod.yml --env-file .env.prod

prod-build: ## Build the two production images, tagged :local
	docker build -t ghcr.io/mbottoni/fundamental-agents-api:local \
		--build-arg APP_VERSION=local backend
	docker build -t ghcr.io/mbottoni/fundamental-agents-web:local frontend

prod-up: prod-build ## Run the production stack locally (PROD_PORT, default 8080)
	$(PROD_COMPOSE) up -d

smoke: ## Run CI's smoke test against the images from prod-build
	ops/smoke-test.sh local local

prod-down: ## Stop the local production stack
	$(PROD_COMPOSE) down

prod-logs: ## Tail the local production stack's logs
	$(PROD_COMPOSE) logs -f

# ══════════════════════════════════════════════════════════════
# Logs
# ══════════════════════════════════════════════════════════════

logs: ## Tail logs for all services
	docker-compose logs -f

logs-backend: ## Tail backend logs
	docker-compose logs -f backend

logs-frontend: ## Tail frontend logs
	docker-compose logs -f frontend

logs-db: ## Tail database logs
	docker-compose logs -f db

# ══════════════════════════════════════════════════════════════
# Shell Access
# ══════════════════════════════════════════════════════════════

shell-backend: ## Open a shell in the backend container
	docker-compose exec backend bash

shell-frontend: ## Open a shell in the frontend container
	docker-compose exec frontend sh

shell-db: ## Open a psql session in the database
	docker-compose exec db psql -U user -d stock-analyzer

# ══════════════════════════════════════════════════════════════
# Testing
# ══════════════════════════════════════════════════════════════

test: test-backend ## Run all tests

test-backend: ## Run backend pytest suite
	docker-compose exec backend pytest -v --tb=short

test-local: ## Run backend tests locally (no Docker)
	cd backend && pytest -v --tb=short

gen-types: ## Regenerate frontend types from the backend's OpenAPI schema
	cd backend && python scripts/dump_openapi.py openapi.json
	cd frontend && npm run gen:types

# ══════════════════════════════════════════════════════════════
# Database Migrations (Alembic)
# ══════════════════════════════════════════════════════════════

migrate: ## Run database migrations (alembic upgrade head)
	docker-compose exec backend alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create MSG="add foo")
	docker-compose exec backend alembic revision --autogenerate -m "$(MSG)"

migrate-history: ## Show migration history
	docker-compose exec backend alembic history

migrate-check: ## Fail if the models and the migrations have drifted apart
	docker-compose exec backend alembic check

# ══════════════════════════════════════════════════════════════
# Quick Smoke Tests
# ══════════════════════════════════════════════════════════════

health: ## Check backend health endpoint
	@curl -s http://localhost:8000/healthz | python3 -m json.tool

test-register: ## Register a test user
	@curl -s -X POST http://localhost:8000/api/v1/auth/register \
		-H "Content-Type: application/json" \
		-d '{"email": "test@example.com", "password": "TestPass123"}' | python3 -m json.tool

test-login: ## Login as test user (prints token)
	@curl -s -X POST http://localhost:8000/api/v1/auth/login \
		-d "username=test@example.com&password=TestPass123" \
		-H "Content-Type: application/x-www-form-urlencoded" | python3 -m json.tool

# ══════════════════════════════════════════════════════════════
# Cleanup
# ══════════════════════════════════════════════════════════════

clean: ## Stop services and remove containers
	docker-compose down --remove-orphans

clean-volumes: ## Stop services and remove all volumes (DELETES DB DATA)
	docker-compose down -v --remove-orphans

reset: ## Full reset: remove everything and rebuild from scratch
	docker-compose down -v --remove-orphans
	docker-compose build --no-cache
	docker-compose up -d

# ══════════════════════════════════════════════════════════════
# Utilities
# ══════════════════════════════════════════════════════════════

secret-key: ## Generate a new SECRET_KEY
	@python3 -c "import secrets; print(secrets.token_urlsafe(64))"

db-tables: ## List all tables in the database
	docker-compose exec db psql -U user -d stock-analyzer -c "\dt"

db-users: ## List all users in the database
	docker-compose exec db psql -U user -d stock-analyzer -c "SELECT id, email, is_verified, subscription_status, created_at FROM users;"

db-jobs: ## List all analysis jobs
	docker-compose exec db psql -U user -d stock-analyzer -c "SELECT id, user_id, ticker, status, created_at FROM analysisjobs ORDER BY created_at DESC;"
