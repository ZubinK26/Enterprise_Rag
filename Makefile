.PHONY: install install-dev lint format test run demo demo-ps docker-build docker-up docker-down pre-commit

PYTHON ?= python

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

install-dev: install
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	$(PYTHON) -m ruff check app tests
	$(PYTHON) -m ruff format --check app tests

format:
	$(PYTHON) -m ruff format app tests
	$(PYTHON) -m ruff check app tests --fix

test:
	$(PYTHON) -m pytest tests -q --tb=short

run:
	$(PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Requires API already running (`make run` or Docker Compose)
demo:
	bash scripts/demo.sh

demo-ps:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/demo.ps1

docker-build:
	docker compose build

docker-up:
	docker compose up --build

docker-down:
	docker compose down

pre-commit:
	pre-commit run --all-files
