.PHONY: setup test build run-backend run-frontend clean-data

PYTHON ?= .venv/bin/python

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r backend/requirements.lock
	npm --prefix frontend ci

test:
	$(PYTHON) -m pytest -q backend/tests
	npm --prefix frontend test -- --run

build:
	npm --prefix frontend run build

run-backend:
	$(PYTHON) -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

run-frontend:
	npm --prefix frontend run dev

clean-data:
	rm -rf backend/data
