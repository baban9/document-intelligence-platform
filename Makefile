.PHONY: setup setup-ocr setup-ui install run run-ui test clean docker-build docker-up docker-down docker-logs

PYTHON := .venv/bin/python
PIP := .venv/bin/pip
PYTEST := .venv/bin/pytest
COMPOSE := docker compose

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

setup-ocr:
	$(PIP) install -e ".[ocr]"
	$(PYTHON) -m spacy download en_core_web_sm

setup-ui:
	$(PIP) install -e ".[ui]"

install:
	$(PIP) install -e ".[dev]"

run:
	$(PYTHON) run.py

run-ui:
	$(PYTHON) run_ui.py

test:
	$(PYTEST) tests/ -q

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache dist build *.egg-info

docker-build:
	$(COMPOSE) build

docker-up:
	$(COMPOSE) up --build -d

docker-down:
	$(COMPOSE) down

docker-logs:
	$(COMPOSE) logs -f

docker-logs-api:
	$(COMPOSE) logs -f api

docker-logs-ui:
	$(COMPOSE) logs -f ui
