# =============================================================================
# ShieldOps Makefile
# AI-Powered Autonomous SRE Platform
# =============================================================================

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

COMPOSE_FILE   := infrastructure/docker/docker-compose.yml
DOCKER_FILE    := infrastructure/docker/Dockerfile
IMAGE_NAME     := shieldops
IMAGE_TAG      ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "latest")
REGISTRY       ?= ""
PYTHON         := python
VENV           := .venv
PIP            := $(VENV)/bin/pip
PYTEST         := $(VENV)/bin/pytest
RUFF           := $(VENV)/bin/ruff
MYPY           := $(VENV)/bin/mypy
ALEMBIC        := $(VENV)/bin/alembic
UVICORN        := $(VENV)/bin/uvicorn
TF_AWS_DIR     := infrastructure/terraform/aws
TF_GCP_DIR     := infrastructure/terraform/gcp
TF_AZURE_DIR   := infrastructure/terraform/azure

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

.PHONY: help
help: ## Show available commands
	@echo ""
	@echo "ShieldOps — Development Commands"
	@echo "================================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

.PHONY: dev
dev: ## Start infrastructure (PostgreSQL, Redis, Kafka, OPA)
	@echo "==> Starting infrastructure services..."
	docker compose -f $(COMPOSE_FILE) up -d postgres redis kafka opa
	@echo "==> Waiting for services to become healthy..."
	@docker compose -f $(COMPOSE_FILE) ps
	@echo ""
	@echo "Infrastructure ready:"
	@echo "  PostgreSQL  localhost:5432"
	@echo "  Redis       localhost:6379"
	@echo "  Kafka       localhost:9092"
	@echo "  OPA         localhost:8181"

.PHONY: dev-all
dev-all: ## Start all services including API via docker-compose
	@echo "==> Starting all services..."
	docker compose -f $(COMPOSE_FILE) up -d
	@echo "==> All services started."

.PHONY: clean
clean: ## Stop all services and remove volumes
	@echo "==> Stopping all containers and removing volumes..."
	docker compose -f $(COMPOSE_FILE) down -v --remove-orphans
	@echo "==> Clean complete."

.PHONY: logs
logs: ## Tail logs from all docker-compose services
	docker compose -f $(COMPOSE_FILE) logs -f

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

.PHONY: setup
setup: venv install migrate seed ## Install all dependencies + run migrations + seed data
	@echo ""
	@echo "==> Setup complete. Run 'make run' to start the application."

.PHONY: venv
venv: ## Create Python virtual environment
	@if [ ! -d "$(VENV)" ]; then \
		echo "==> Creating virtual environment..."; \
		$(PYTHON) -m venv $(VENV); \
	else \
		echo "==> Virtual environment already exists."; \
	fi

.PHONY: install
install: venv ## Install Python and frontend dependencies
	@echo "==> Installing Python dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	@echo "==> Installing frontend dependencies..."
	cd dashboard-ui && npm install

.PHONY: migrate
migrate: ## Run database migrations
	@echo "==> Running database migrations..."
	$(ALEMBIC) upgrade head
	@echo "==> Migrations complete."

.PHONY: seed
seed: ## Seed demo data (admin user, sample agents, historical data)
	@echo "==> Seeding demo data..."
	$(VENV)/bin/python -m shieldops.db.seed || echo "Seeding skipped (module may not exist yet)."

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

.PHONY: run
run: ## Start API server + frontend dev server
	@echo "==> Starting ShieldOps..."
	@echo "    API:       http://localhost:8000"
	@echo "    Dashboard: http://localhost:3000"
	@echo "    API Docs:  http://localhost:8000/api/v1/docs"
	@echo ""
	@trap 'kill 0' EXIT; \
		$(UVICORN) shieldops.api.app:app --host 0.0.0.0 --port 8000 --reload & \
		cd dashboard-ui && npm run dev & \
		wait

.PHONY: run-api
run-api: ## Start API server only
	$(UVICORN) shieldops.api.app:app --host 0.0.0.0 --port 8000 --reload

.PHONY: run-frontend
run-frontend: ## Start frontend dev server only
	cd dashboard-ui && npm run dev

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

.PHONY: test
test: ## Run full test suite with coverage
	@echo "==> Running full test suite..."
	$(PYTEST) tests/ \
		--cov=src/shieldops \
		--cov-report=term-missing \
		--cov-fail-under=80 \
		--junitxml=junit.xml

.PHONY: test-unit
test-unit: ## Run unit tests only
	@echo "==> Running unit tests..."
	$(PYTEST) tests/unit/ -v

.PHONY: test-integration
test-integration: ## Run integration tests only (requires infrastructure)
	@echo "==> Running integration tests..."
	$(PYTEST) tests/integration/ -v -m integration

.PHONY: test-agents
test-agents: ## Run agent simulation tests
	@echo "==> Running agent simulation tests..."
	$(PYTEST) tests/agents/ -v

# ---------------------------------------------------------------------------
# Code Quality
# ---------------------------------------------------------------------------

.PHONY: lint
lint: ## Run ruff check + mypy
	@echo "==> Linting with ruff..."
	$(RUFF) check src/ tests/
	@echo "==> Type checking with mypy..."
	$(MYPY) src/shieldops/

.PHONY: format
format: ## Run ruff format (auto-fix)
	@echo "==> Formatting with ruff..."
	$(RUFF) format src/ tests/
	$(RUFF) check --fix src/ tests/

.PHONY: typecheck
typecheck: ## Run mypy type checker
	@echo "==> Running mypy..."
	$(MYPY) src/shieldops/

.PHONY: lint-frontend
lint-frontend: ## Run ESLint on frontend code
	@echo "==> Linting frontend..."
	cd dashboard-ui && npm run lint

.PHONY: check
check: lint lint-frontend test ## Run all checks (lint + typecheck + test)
	@echo "==> All checks passed."

# ---------------------------------------------------------------------------
# Build & Push
# ---------------------------------------------------------------------------

.PHONY: build
build: ## Build Docker image
	@echo "==> Building Docker image $(IMAGE_NAME):$(IMAGE_TAG)..."
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) -f $(DOCKER_FILE) .
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(IMAGE_NAME):latest
	@echo "==> Build complete: $(IMAGE_NAME):$(IMAGE_TAG)"

.PHONY: build-frontend
build-frontend: ## Build frontend for production
	@echo "==> Building frontend..."
	cd dashboard-ui && npm run build

.PHONY: push
push: ## Push Docker image to registry (set REGISTRY env var)
	@if [ -z "$(REGISTRY)" ]; then \
		echo "ERROR: Set REGISTRY env var (e.g., REGISTRY=123456789.dkr.ecr.us-east-1.amazonaws.com)"; \
		exit 1; \
	fi
	@echo "==> Pushing $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)..."
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
	docker push $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
	@echo "==> Push complete."

# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------

.PHONY: deploy-staging
deploy-staging: ## Deploy to staging via Terraform (AWS)
	@echo "==> Deploying to staging..."
	cd $(TF_AWS_DIR) && \
		terraform init && \
		terraform plan -var-file=environments/staging.tfvars -out=staging.tfplan && \
		terraform apply staging.tfplan
	@echo "==> Staging deployment complete."

.PHONY: deploy-prod
deploy-prod: ## Deploy to production (with confirmation)
	@echo ""
	@echo "  WARNING: You are about to deploy to PRODUCTION."
	@echo ""
	@read -p "  Type 'yes' to continue: " confirm && \
		[ "$$confirm" = "yes" ] || (echo "Aborted." && exit 1)
	@echo "==> Deploying to production..."
	cd $(TF_AWS_DIR) && \
		terraform init && \
		terraform plan -var-file=environments/production.tfvars -out=prod.tfplan && \
		terraform apply prod.tfplan
	@echo "==> Production deployment complete."

# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------

.PHONY: docs
docs: ## Generate and open API docs
	@echo "==> API docs available at http://localhost:8000/api/v1/docs"
	@echo "    (Requires the API server to be running: make run-api)"
	@echo ""
	@echo "==> Generating OpenAPI spec..."
	$(VENV)/bin/python -c "\
		from shieldops.api.app import app; \
		import json; \
		spec = app.openapi(); \
		print(json.dumps(spec, indent=2))" > docs/openapi.json 2>/dev/null \
		&& echo "    Written to docs/openapi.json" \
		|| echo "    Skipped (start API server for live docs)."

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

.PHONY: db-shell
db-shell: ## Open a psql shell to the local database
	docker exec -it $$(docker compose -f $(COMPOSE_FILE) ps -q postgres) \
		psql -U shieldops -d shieldops

.PHONY: redis-cli
redis-cli: ## Open a redis-cli shell
	docker exec -it $$(docker compose -f $(COMPOSE_FILE) ps -q redis) redis-cli

.PHONY: migration
migration: ## Create a new Alembic migration (usage: make migration MSG="add users table")
	@if [ -z "$(MSG)" ]; then \
		echo "ERROR: Set MSG (e.g., make migration MSG=\"add users table\")"; \
		exit 1; \
	fi
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"
	@echo "==> Migration created. Review it in alembic/versions/."
