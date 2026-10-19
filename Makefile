.PHONY: setup doctor test build runner-build docker-build docker-run docker-up docker-down run-backend run-frontend clean-data

PYTHON ?= .venv/bin/python
PYTHON_BIN ?= python3
# Docker Desktop may install its CLI outside the shell's PATH. Do not change PATH.
DOCKER ?= $(or $(shell command -v docker 2>/dev/null),$(wildcard /usr/local/bin/docker),docker)

setup:
	"$(PYTHON_BIN)" -m venv .venv
	"$(PYTHON)" -m pip install -r backend/requirements.lock
	npm --prefix frontend ci

doctor:
	"$(PYTHON_BIN)" scripts/doctor.py --python "$(PYTHON)" --docker "$(DOCKER)"

test:
	PYTHONPATH=backend "$(PYTHON)" -m pytest -q backend/tests
	npm --prefix frontend test -- --run

build:
	npm --prefix frontend run build

docker-build:
	"$(DOCKER)" build --tag code-aid-api:0.1.0 .

runner-build:
	"$(DOCKER)" build --file execution/Dockerfile --tag code-aid-runner:0.1.0 .

docker-run:
	"$(DOCKER)" run --rm --publish 127.0.0.1:8000:8000 --volume code_aid_data:/app/backend/data code-aid-api:0.1.0

docker-up:
	"$(DOCKER)" compose up --build --detach --wait

docker-down:
	"$(DOCKER)" compose down

run-backend:
	"$(PYTHON)" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

run-frontend:
	npm --prefix frontend run dev

clean-data:
	rm -rf backend/data
