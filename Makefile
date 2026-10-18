.PHONY: setup test build docker-build docker-run run-backend run-frontend clean-data

PYTHON ?= .venv/bin/python

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r backend/requirements.lock
	npm --prefix frontend ci

test:
	PYTHONPATH=backend $(PYTHON) -m pytest -q backend/tests
	npm --prefix frontend test -- --run

build:
	npm --prefix frontend run build

docker-build:
	docker build --tag code-aid-api:0.1.0 .

docker-run:
	docker run --rm --publish 8000:8000 --volume code_aid_data:/app/backend/data code-aid-api:0.1.0

run-backend:
	$(PYTHON) -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

run-frontend:
	npm --prefix frontend run dev

clean-data:
	rm -rf backend/data
