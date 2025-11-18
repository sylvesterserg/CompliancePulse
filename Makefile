SHELL := /bin/sh

# Tooling detection (macOS/Linux compatible)
PYTHON := $(shell command -v python3 || command -v python)
HAVE_UV := $(shell command -v uv >/dev/null 2>&1 && echo 1 || echo 0)
HAVE_POETRY := $(shell [ -f pyproject.toml ] && command -v poetry >/dev/null 2>&1 && echo 1 || echo 0)

VENV_DIR := .venv
VENV_PY := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
PYTEST := $(VENV_DIR)/bin/pytest
RUFF := $(VENV_DIR)/bin/ruff
BLACK := $(VENV_DIR)/bin/black
ISORT := $(VENV_DIR)/bin/isort

# Compose detection: docker-compose, docker compose, or podman-compose
COMPOSE := $(shell \
  if command -v docker-compose >/dev/null 2>&1; then \
    echo docker-compose; \
  elif docker compose version >/dev/null 2>&1; then \
    echo "docker compose"; \
  elif command -v podman-compose >/dev/null 2>&1; then \
    echo podman-compose; \
  else \
    echo ""; \
  fi)

.PHONY: install dev test lint format build up down logs clean

install:
	@if [ "$(HAVE_UV)" = "1" ]; then \
		echo "[install] Using uv"; \
		uv pip install -r backend/requirements.txt; \
		uv pip install -U pytest ruff black isort; \
	elif [ "$(HAVE_POETRY)" = "1" ]; then \
		echo "[install] Using poetry"; \
		poetry install --no-root; \
	else \
		echo "[install] Using venv + pip"; \
		if [ ! -d "$(VENV_DIR)" ]; then \
			"$(PYTHON)" -m venv "$(VENV_DIR)"; \
		fi; \
		"$(VENV_PIP)" install --upgrade pip; \
		"$(VENV_PIP)" install -r backend/requirements.txt; \
		"$(VENV_PIP)" install -U pytest ruff black isort; \
	fi

dev: install
	@echo "[dev] Starting FastAPI with reload"
	@if [ -x "$(VENV_PY)" ]; then \
		"$(VENV_PY)" -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000; \
	elif [ "$(HAVE_POETRY)" = "1" ]; then \
		poetry run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000; \
	else \
		uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000; \
	fi

test: install
	@echo "[test] Running pytest"
	@if [ -x "$(PYTEST)" ]; then \
		"$(PYTEST)" -q -ra --durations=10; \
	elif [ "$(HAVE_POETRY)" = "1" ]; then \
		poetry run pytest -q -ra --durations=10; \
	else \
		pytest -q -ra --durations=10; \
	fi

lint: install
	@echo "[lint] Running ruff (and black --check if available)"
	@if [ -x "$(RUFF)" ]; then \
		"$(RUFF)" check backend tests; \
	else \
		ruff check backend tests; \
	fi; \
	if [ -x "$(BLACK)" ]; then \
		"$(BLACK)" --check backend tests; \
	elif command -v black >/dev/null 2>&1; then \
		black --check backend tests; \
	fi

format: install
	@echo "[format] Applying ruff fixes and formatting"
	@if [ -x "$(RUFF)" ]; then \
		"$(RUFF)" check backend tests --fix; \
		"$(RUFF)" format backend tests; \
	else \
		ruff check backend tests --fix || true; \
		ruff format backend tests || true; \
	fi; \
	if [ -x "$(ISORT)" ]; then \
		"$(ISORT)" backend tests; \
	elif command -v isort >/dev/null 2>&1; then \
		isort backend tests; \
	fi; \
	if [ -x "$(BLACK)" ]; then \
		"$(BLACK)" backend tests; \
	elif command -v black >/dev/null 2>&1; then \
		black backend tests; \
	fi

build:
	@echo "[build] Building containers with compose"
	@if [ -z "$(COMPOSE)" ]; then \
		echo "No compose tool found (docker-compose, docker compose, or podman-compose)."; \
		exit 1; \
	fi; \
	$(COMPOSE) -f docker-compose.yml build

up:
	@echo "[up] Starting stack with compose"
	@if [ -z "$(COMPOSE)" ]; then \
		echo "No compose tool found (docker-compose, docker compose, or podman-compose)."; \
		exit 1; \
	fi; \
	$(COMPOSE) -f docker-compose.yml up -d

down:
	@echo "[down] Stopping stack with compose"
	@if [ -z "$(COMPOSE)" ]; then \
		echo "No compose tool found (docker-compose, docker compose, or podman-compose)."; \
		exit 1; \
	fi; \
	$(COMPOSE) -f docker-compose.yml down

logs:
	@echo "[logs] Tailing compose logs"
	@if [ -z "$(COMPOSE)" ]; then \
		echo "No compose tool found (docker-compose, docker compose, or podman-compose)."; \
		exit 1; \
	fi; \
	$(COMPOSE) -f docker-compose.yml logs -f --tail=200

clean:
	@echo "[clean] Removing caches and artifacts"
	@rm -rf .pytest_cache **/__pycache__ **/*.pyc build dist .ruff_cache || true
	@echo "[clean] To remove virtualenv as well: rm -rf $(VENV_DIR)"

