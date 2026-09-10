PYTHON ?= python
NPM ?= npm

.PHONY: install backend frontend test lint typecheck frontend-check docker-up docker-real

install:
	$(PYTHON) -m pip install -e ".[dev]"
	cd ui && $(NPM) ci

backend:
	$(PYTHON) -m uvicorn api.server:app --reload --host 127.0.0.1 --port 8000

frontend:
	cd ui && $(NPM) run dev

test:
	$(PYTHON) -m pytest
	cd ui && $(NPM) test -- --run

lint:
	$(PYTHON) -m ruff check .
	cd ui && $(NPM) run lint

typecheck:
	$(PYTHON) -m mypy agent api tools utils
	cd ui && $(NPM) run typecheck

frontend-check:
	cd ui && $(NPM) run lint
	cd ui && $(NPM) run typecheck
	cd ui && $(NPM) test -- --run
	cd ui && $(NPM) run build

docker-up:
	docker compose up --build

docker-real:
	docker compose --profile real up --build
