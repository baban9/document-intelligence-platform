.PHONY: setup setup-hooks setup-ocr setup-pii setup-llm setup-jobs setup-auth setup-ui install fix-editable-pth run run-redis run-worker run-ui ui-dev ui-build test eval build-dist publish-pypi clean env-init check-ports check-secrets up up-ocr down up-status generate-corpus scale-test-up scale-test scale-test-down docker-build docker-build-ocr docker-up docker-up-core docker-up-ui docker-up-ocr docker-up-local docker-up-full docker-down docker-logs docker-logs-api docker-logs-ui

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
	$(PYTHON) -m spacy download en_core_web_sm

setup-pii:
	$(PIP) install -e ".[pii]"
	$(PYTHON) -m spacy download en_core_web_sm

setup-llm:
	$(PIP) install -e ".[llm]"

setup-jobs:
	$(PIP) install -e ".[jobs]"

setup-auth:
	$(PIP) install -e ".[auth]"

setup-ui:
	$(PIP) install -e ".[ui]"

install:
	$(PIP) install -e ".[dev]"
	$(MAKE) fix-editable-pth

run:
	$(PYTHON) run.py

run-redis:
	$(COMPOSE) up -d redis

run-worker:
	$(PYTHON) run_worker.py

run-ui:
	$(PYTHON) run_ui.py

# React + Vite UI (professional shell; Process pipeline first). Requires Node 20+.
ui-dev:
	cd frontend && npm install && npm run dev

ui-build:
	cd frontend && npm install && npm run build

test:
	$(PYTEST) tests/ -q

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
check-ports:
	@for spec in \
		"DOCINTEL_PORT:$${DOCINTEL_PORT:-5000}:API" \
		"GRADIO_PORT:$${GRADIO_PORT:-7860}:Gradio UI"; do \
		name=$${spec%%:*}; rest=$${spec#*:}; \
		port=$${rest%%:*}; label=$${rest#*:}; \
		if lsof -nP -iTCP:$$port -sTCP:LISTEN >/dev/null 2>&1; then \
			echo "Port $$port ($$label) is already in use."; \
			echo "Edit .env (run: make env-init) and set $$name to a free port, then run make up again."; \
			echo "Example: $$name=5001"; \
			lsof -nP -iTCP:$$port -sTCP:LISTEN | head -3; \
			exit 1; \
		fi; \
	done

# Full local stack: Redis, slim API, worker, Gradio UI.
# Use make up-ocr for scanned PDF OCR (large PyTorch download).
up: docker-up-local

up-ocr: check-ports
	DOCINTEL_DOCKER_TARGET=ocr $(COMPOSE) --profile ui up -d --build
	@$(MAKE) --no-print-directory up-status

down: docker-down

up-status:
	@echo ""
	@echo "Document Intelligence local stack (DOCINTEL_DOCKER_TARGET=$${DOCINTEL_DOCKER_TARGET:-slim})"
	@$(COMPOSE) --profile ui ps
	@echo ""
	@echo "URLs:"
	@echo "  API        http://127.0.0.1:$${DOCINTEL_PORT:-5000}"
	@echo "  API docs   http://127.0.0.1:$${DOCINTEL_PORT:-5000}/docs"
	@echo "  Gradio UI  http://127.0.0.1:$${GRADIO_PORT:-7860}"
	@echo "  React UI   http://127.0.0.1:5173  (make ui-dev, API must be running)"
	@echo "  Metrics    http://127.0.0.1:$${DOCINTEL_PORT:-5000}/metrics?format=prometheus"
	@echo "  Redis      localhost:$${REDIS_PORT:-6379}"
	@echo "  Monitoring integration: docs/MONITORING.md"
	@if [ "$${DOCINTEL_DOCKER_TARGET:-slim}" = "slim" ]; then \
		echo ""; \
		echo "Scanned PDF OCR is not in this image. Run: make up-ocr"; \
	fi
	@echo ""

docker-build:
	DOCINTEL_DOCKER_TARGET=slim $(COMPOSE) build api

docker-build-ocr:
	DOCINTEL_DOCKER_TARGET=ocr $(COMPOSE) build api worker

docker-up-core:
	$(COMPOSE) up -d redis
	$(COMPOSE) up -d --build api
	$(COMPOSE) up -d worker

docker-up:
	$(COMPOSE) up -d --build redis api worker

docker-up-ui:
	$(COMPOSE) --profile ui up -d --build ui

docker-up-ocr:
	DOCINTEL_DOCKER_TARGET=ocr $(COMPOSE) up -d --build redis api worker

docker-up-local: check-ports
	$(COMPOSE) --profile ui up -d --build
	@$(MAKE) --no-print-directory up-status

docker-up-full:
	DOCINTEL_DOCKER_TARGET=ocr $(COMPOSE) --profile ui up -d --build
	@$(MAKE) --no-print-directory up-status

docker-down:
	$(COMPOSE) --profile ui down

docker-logs:
	$(COMPOSE) logs -f

docker-logs-api:
	$(COMPOSE) logs -f api

docker-logs-ui:
	$(COMPOSE) logs -f ui

generate-corpus:
	$(PYTHON) scripts/generate_test_corpus.py

scale-test-up: check-ports
	$(COMPOSE) -f docker-compose.yml -f docker-compose.scale-test.yml up -d --build redis api worker
	@echo ""
	@echo "Scale test stack (500 MB RAM cap on api + worker). Generate corpus: make generate-corpus"
	@echo "Run load test: make scale-test"
	@echo "Docs: docs/SCALE_TESTING.md"

scale-test:
	$(PYTHON) scripts/scale_test.py --report eval/reports/scale_report.json

scale-test-down:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.scale-test.yml down
