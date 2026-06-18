.PHONY: setup setup-hooks setup-ocr setup-pii setup-llm setup-jobs setup-auth setup-ui install run run-redis run-worker run-ui test eval build-dist publish-pypi clean docker-build docker-build-ocr docker-up docker-up-core docker-up-ui docker-up-ocr docker-up-full docker-down docker-logs docker-logs-api docker-logs-ui

PYTHON := .venv/bin/python
PIP := .venv/bin/pip
PYTEST := .venv/bin/pytest
COMPOSE := docker compose

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

setup-hooks:
	git config core.hooksPath .githooks

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

run:
	$(PYTHON) run.py

run-redis:
	$(COMPOSE) up -d redis

run-worker:
	$(PYTHON) run_worker.py

run-ui:
	$(PYTHON) run_ui.py

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

docker-up-full:
	DOCINTEL_DOCKER_TARGET=ocr $(COMPOSE) --profile ui up -d --build

docker-down:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f

docker-logs-api:
	$(COMPOSE) logs -f api

docker-logs-ui:
	$(COMPOSE) logs -f ui
