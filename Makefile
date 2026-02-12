.PHONY: help up down build restart logs logs-backend logs-frontend logs-db \
       shell-backend shell-frontend shell-db \
       health register test-api \
       clean clean-volumes reset \
       lint format

# --- Default ---
help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Docker Compose ---
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

# --- Logs ---
logs: ## Tail logs for all services
	docker-compose logs -f

logs-backend: ## Tail backend logs
	docker-compose logs -f backend

logs-frontend: ## Tail frontend logs
	docker-compose logs -f frontend

logs-db: ## Tail database logs
	docker-compose logs -f db

# --- Shell Access ---
shell-backend: ## Open a shell in the backend container
	docker-compose exec backend bash

shell-frontend: ## Open a shell in the frontend container
	docker-compose exec frontend sh

shell-db: ## Open a psql session in the database
	docker-compose exec db psql -U user -d stock-analyzer

# --- Quick Tests ---
health: ## Check backend health endpoint
	@curl -s http://localhost:8000/health | python3 -m json.tool

test-register: ## Register a test user
	@curl -s -X POST http://localhost:8000/api/v1/auth/register \
		-H "Content-Type: application/json" \
		-d '{"email": "test@example.com", "password": "TestPass123"}' | python3 -m json.tool

test-login: ## Login as test user (prints token)
	@curl -s -X POST http://localhost:8000/api/v1/auth/login \
		-d "username=test@example.com&password=TestPass123" \
		-H "Content-Type: application/x-www-form-urlencoded" | python3 -m json.tool

# --- Cleanup ---
clean: ## Stop services and remove containers
	docker-compose down --remove-orphans

clean-volumes: ## Stop services and remove all volumes (DELETES DB DATA)
	docker-compose down -v --remove-orphans

reset: ## Full reset: remove everything and rebuild from scratch
	docker-compose down -v --remove-orphans
	docker-compose build --no-cache
	docker-compose up -d

# --- Utilities ---
secret-key: ## Generate a new SECRET_KEY
	@python3 -c "import secrets; print(secrets.token_urlsafe(64))"

db-tables: ## List all tables in the database
	docker-compose exec db psql -U user -d stock-analyzer -c "\dt"

db-users: ## List all users in the database
	docker-compose exec db psql -U user -d stock-analyzer -c "SELECT id, email, subscription_status, created_at FROM users;"

db-jobs: ## List all analysis jobs
	docker-compose exec db psql -U user -d stock-analyzer -c "SELECT id, user_id, ticker, status, created_at FROM analysisjobs ORDER BY created_at DESC;"
