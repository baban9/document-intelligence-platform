.PHONY: setup setup-hooks setup-ocr setup-pii setup-llm setup-jobs setup-auth setup-ui install fix-editable-pth run run-redis run-worker run-ui ui-dev ui-build test test-postgres eval build-dist publish-pypi clean env-init check-ports check-secrets up up-ocr down up-status up-logs-tail launch wait-healthy e2e generate-corpus scale-test-up scale-test scale-test-down docker-build-base docker-build-base-ocr docker-ensure-base docker-build docker-build-ocr docker-up docker-up-core docker-up-ui docker-up-ocr docker-up-local docker-up-full docker-down docker-logs docker-logs-api docker-logs-ui docker-logs-worker clean-legacy-monitoring

PYTHON := .venv/bin/python
PIP := .venv/bin/pip
PYTEST := .venv/bin/pytest
COMPOSE := docker compose
export PYTHONPATH := $(CURDIR)/src

# Load .env so DOCINTEL_PORT and other vars apply to compose and up-status.
ifneq (,$(wildcard .env))
  include .env
  export
endif

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e ".[dev]"
	$(MAKE) fix-editable-pth
	$(MAKE) setup-hooks

fix-editable-pth:
	@for pth in .venv/lib/python*/site-packages/__editable__*.pth; do \
		if [ -f "$$pth" ]; then chflags nohidden "$$pth" 2>/dev/null || true; fi; \
	done

setup-hooks:
	chmod +x .githooks/commit-msg .githooks/prepare-commit-msg .githooks/pre-commit .githooks/scan-secrets.sh .githooks/scan-tracked-secrets.sh
	git config core.hooksPath .githooks

check-secrets:
	@.githooks/scan-tracked-secrets.sh
	@echo "secret-scan: no secrets found in tracked files"

setup-ocr:
	$(PIP) install -e ".[pii]"
	$(PIP) install torch --index-url https://download.pytorch.org/whl/cpu
	$(PIP) install -e ".[ocr]"
	$(PYTHON) -m spacy download en_core_web_lg

setup-pii:
	$(PIP) install -e ".[pii]"
	$(PYTHON) -m spacy download en_core_web_lg

setup-llm:
	$(PIP) install -e ".[llm]"

setup-jobs:
	$(PIP) install -e ".[jobs]"

setup-auth:
	$(PIP) install -e ".[auth]"

setup-ui:
	cd frontend && npm install

install:
	$(PIP) install -e ".[dev]"
	$(MAKE) fix-editable-pth

run:
	$(PYTHON) run.py

run-redis:
	$(COMPOSE) up -d redis

run-worker:
	$(PYTHON) run_worker.py

run-ui: ui-dev

# React + Vite UI (local dev with hot reload). Requires Node 20+.
ui-dev:
	cd frontend && npm install && npm run dev

ui-build:
	cd frontend && npm install && npm run build

test:
	$(PYTEST) tests/ -q

# Requires Postgres (make up or docker compose up -d postgres).
test-postgres:
	@if [ -z "$$DOCINTEL_DATABASE_URL" ]; then \
		export DOCINTEL_DATABASE_URL=postgresql://docintel:docintel@127.0.0.1:5432/docintel; \
	fi; \
	$(COMPOSE) up -d postgres; \
	DOCINTEL_DATABASE_URL=$${DOCINTEL_DATABASE_URL:-postgresql://docintel:docintel@127.0.0.1:5432/docintel} \
	DOCINTEL_MULTI_TENANT=true \
	$(PYTEST) tests/test_tenant_context.py tests/test_tenant_routes.py tests/test_tenant_jobs.py -q

eval:
	$(PYTHON) eval/run_eval.py

build-dist:
	$(PYTHON) -m build

publish-pypi: build-dist
	$(PYTHON) -m twine upload dist/*

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache dist build *.egg-info

env-init:
	@if [ -f .env ]; then \
		echo ".env already exists"; \
	else \
		cp .env.example .env; \
		echo "Created .env from .env.example"; \
	fi

# Fail early when host ports are taken (avoids opaque docker bind errors).
# Skips ports still held by this compose project (run make down first to recycle).
check-ports:
	@for spec in \
		"DOCINTEL_PORT:$${DOCINTEL_PORT:-5000}:API" \
		"UI_PORT:$${UI_PORT:-8080}:Web UI"; do \
		name=$${spec%%:*}; rest=$${spec#*:}; \
		port=$${rest%%:*}; label=$${rest#*:}; \
		if lsof -nP -iTCP:$$port -sTCP:LISTEN >/dev/null 2>&1; then \
			if $(COMPOSE) ps --format '{{.Ports}}' 2>/dev/null | grep -q ":$$port->"; then \
				echo "Port $$port ($$label) is in use by this stack; recycling containers..."; \
			else \
				echo "Port $$port ($$label) is already in use."; \
				echo "If a previous stack is running: make down"; \
				echo "Or edit .env (make env-init) and set $$name to a free port."; \
				echo "Example: $$name=8081"; \
				lsof -nP -iTCP:$$port -sTCP:LISTEN | head -3; \
				exit 1; \
			fi; \
		fi; \
	done

# Full local stack: Redis, slim API, worker, React UI.
# Use make up-ocr for scanned PDF OCR (large PyTorch download).
# Set LOGS=0 to skip the log tail after startup (useful in CI).
# Use make launch for detached startup + health wait + e2e smoke test.
up: docker-up-local

launch: env-init
	LOGS=0 $(MAKE) docker-up-local
	@$(MAKE) wait-healthy
	@$(MAKE) e2e
	@echo ""
	@echo "Launch complete."
	@echo "  Web UI  http://127.0.0.1:$${UI_PORT:-8080}"
	@echo "  API     http://127.0.0.1:$${DOCINTEL_PORT:-5000}"
	@echo "  Logs    make docker-logs"

wait-healthy:
	$(PYTHON) scripts/wait_for_stack.py \
		--api-base "http://127.0.0.1:$${DOCINTEL_PORT:-5000}" \
		--ui-base "http://127.0.0.1:$${UI_PORT:-8080}"

e2e:
	$(PYTHON) scripts/e2e_test.py \
		--api-base "http://127.0.0.1:$${DOCINTEL_PORT:-5000}" \
		--ui-base "http://127.0.0.1:$${UI_PORT:-8080}"

up-ocr: docker-down check-ports
	DOCINTEL_DOCKER_TARGET=ocr $(COMPOSE) up -d --build redis api worker ui
	@$(MAKE) --no-print-directory up-status
	@$(MAKE) --no-print-directory up-logs-tail

down: docker-down

up-status:
	@echo ""
	@echo "Document Intelligence local stack (DOCINTEL_DOCKER_TARGET=$${DOCINTEL_DOCKER_TARGET:-slim})"
	@$(COMPOSE) ps
	@echo ""
	@echo "URLs:"
	@echo "  Web UI     http://127.0.0.1:$${UI_PORT:-8080}"
	@echo "  API        http://127.0.0.1:$${DOCINTEL_PORT:-5000}"
	@echo "  API docs   http://127.0.0.1:$${DOCINTEL_PORT:-5000}/docs"
	@echo "  Dev UI     http://127.0.0.1:5173  (make ui-dev, hot reload)"
	@echo "  Metrics    http://127.0.0.1:$${DOCINTEL_PORT:-5000}/metrics?format=prometheus"
	@echo "  Redis      localhost:$${REDIS_PORT:-6379}"
	@echo "  Monitoring integration: docs/MONITORING.md"
	@echo ""
	@echo "Logs:"
	@echo "  make launch              start stack, wait for health, run e2e smoke test"
	@echo "  make e2e                 run e2e against a running stack"
	@echo "  make docker-logs         follow all services (Ctrl+C to stop following)"
	@echo "  make docker-logs-api     API only"
	@echo "  make docker-logs-ui      web UI only"
	@echo "  make docker-logs-worker  worker only"
	@if docker ps --format '{{.Names}}' 2>/dev/null | grep -q 'document-intelligence-platform-grafana-1'; then \
		echo ""; \
		echo "Old Grafana/Prometheus containers are still running from a prior stack."; \
		echo "Stop them with: make clean-legacy-monitoring"; \
	fi
	@if [ "$${DOCINTEL_DOCKER_TARGET:-slim}" = "slim" ]; then \
		echo ""; \
		echo "Scanned PDF OCR is not in this image. Run: make up-ocr"; \
	fi
	@echo ""

docker-build-base:
	$(COMPOSE) -f docker-compose.base.yml build platform-base-slim

docker-build-base-ocr:
	$(COMPOSE) -f docker-compose.base.yml build platform-base-slim platform-base-ocr

docker-ensure-base:
	@docker image inspect docintel-platform-base:3.11-slim >/dev/null 2>&1 || $(MAKE) docker-build-base

docker-ensure-base-ocr:
	@docker image inspect docintel-platform-base:3.11-ocr >/dev/null 2>&1 || $(MAKE) docker-build-base-ocr

docker-build: docker-ensure-base
	DOCINTEL_DOCKER_TARGET=slim $(COMPOSE) build api

docker-build-ocr: docker-ensure-base-ocr
	DOCINTEL_DOCKER_TARGET=ocr $(COMPOSE) build api worker

docker-up-core:
	$(COMPOSE) up -d redis
	$(COMPOSE) up -d --build api
	$(COMPOSE) up -d worker

docker-up:
	$(COMPOSE) up -d --build redis api worker

docker-up-ui:
	$(COMPOSE) up -d --build ui

docker-up-ocr:
	DOCINTEL_DOCKER_TARGET=ocr $(MAKE) docker-ensure-base-ocr
	DOCINTEL_DOCKER_TARGET=ocr $(COMPOSE) up -d --build redis api worker

docker-up-local: docker-down check-ports docker-ensure-base
	$(COMPOSE) up -d --build postgres redis api worker ui
	@$(MAKE) --no-print-directory up-status
	@$(MAKE) --no-print-directory up-logs-tail

docker-up-full: docker-down docker-ensure-base-ocr
	DOCINTEL_DOCKER_TARGET=ocr $(COMPOSE) up -d --build redis api worker ui
	@$(MAKE) --no-print-directory up-status
	@$(MAKE) --no-print-directory up-logs-tail

# Recent log snapshot plus live follow (containers stay up if you Ctrl+C).
up-logs-tail:
ifneq ($(LOGS),0)
	@echo ""
	@echo "Recent logs (last 40 lines per service):"
	@$(COMPOSE) logs --tail=40
	@echo ""
	@echo "Following live logs (Ctrl+C stops follow; containers keep running):"
	@$(COMPOSE) logs -f
endif

docker-down:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f

docker-logs-api:
	$(COMPOSE) logs -f api

docker-logs-ui:
	$(COMPOSE) logs -f ui

docker-logs-worker:
	$(COMPOSE) logs -f worker

# Stop orphaned Grafana/Prometheus from older compose files (not part of make up anymore).
clean-legacy-monitoring:
	@docker rm -f document-intelligence-platform-grafana-1 document-intelligence-platform-prometheus-1 2>/dev/null || true
	@echo "Removed legacy monitoring containers if they were running."

generate-corpus:
	$(PYTHON) scripts/generate_test_corpus.py

scale-test-up: docker-down check-ports
	$(COMPOSE) -f docker-compose.yml -f docker-compose.scale-test.yml up -d --build redis api worker
	@echo ""
	@echo "Scale test stack (500 MB RAM cap on api + worker). Generate corpus: make generate-corpus"
	@echo "Run load test: make scale-test"
	@echo "Docs: docs/SCALE_TESTING.md"

scale-test:
	$(PYTHON) scripts/scale_test.py --report eval/reports/scale_report.json

scale-test-down:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.scale-test.yml down
