# Code-Aid backend

The backend is a Python 3.9-compatible FastAPI service for safe, deterministic
Python traceback investigations. It parses uploaded source as data, performs
AST analysis, ranks reproducible hypotheses, generates pytest source without
executing it on the host, and persists every result in SQLite.

## Setup

```bash
cd backend
python3.9 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The pinned `requirements.txt` (also copied to `requirements.lock`) is the
project lockfile. No model provider or external API is required.

## Run

From `backend/`:

```bash
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

The service defaults to the bundled `../samples` directory and stores SQLite
data and ingested projects under `backend/data/`. Copy `.env.example` to
`.env` only when environment overrides are needed; the app reads environment
variables directly.

## Test

The single offline check is:

```bash
make test
```

Tests use only the pinned local dependencies and do not require Docker. Docker
is intentionally optional for the run-tests endpoint; without it the endpoint
returns an `unavailable` result and never executes project code on the host.

## API contract

The canonical routes are under `/api`; identical root aliases are provided for
simple local React proxy setups. FastAPI publishes the interactive contract at
`/api/docs` and the OpenAPI document at `/api/openapi.json` when the app is
served through a proxy that preserves the `/api` prefix (the app itself also
serves `/docs` and `/openapi.json`).

### System and samples

| Method | Route | Behavior |
| --- | --- | --- |
| `GET` | `/api/health` | Returns service/version/database health. |
| `GET` | `/api/samples` | Lists safe bundled sample choices and their metadata/traceback. |
| `GET` | `/api/samples/{sample_id}` | Returns one sample descriptor. |

### Investigations

| Method | Route | Body / result |
| --- | --- | --- |
| `GET` | `/api/investigations?limit=100&offset=0` | Lists persisted summaries. |
| `POST` | `/api/investigations` | Accepts JSON or multipart. Choose exactly one `sample_id` (or `sample`) **or** a `.zip` file field named `archive`, `file`, `zip_file`, or `project`; optional `title`/`name` and `traceback`/`traceback_text` are accepted. JSON may carry the ZIP as `archive_base64` plus optional `filename`. |
| `GET` | `/api/investigations/{id}` | Returns the full persisted investigation. |
| `DELETE` | `/api/investigations/{id}` | Deletes the record and its private ingested project directory. |
| `POST` | `/api/investigations/{id}/run-tests` | Optional JSON `{ "timeout_seconds": 20 }`; executes generated tests only in Docker and appends an execution result. |
| `POST` | `/api/investigations/{id}/verify` | JSON `{ "file_path": "module.py", "content": "..." }` (or `path`) checks a proposed change without mutating the stored project and, when Docker is available, compares baseline and staged-patch test runs. |
| `GET` | `/api/investigations/{id}/report` | Downloads a `text/markdown` report. |

Creation returns an object with these deliberately separate result sections:

```json
{
  "id": "uuid",
  "source": { "source_type": "sample", "sample_id": "...", "traceback": "..." },
  "results": {
    "facts": [],
    "findings": [],
    "hypotheses": [],
    "generated_tests": [],
    "execution_results": [],
    "verification": { "status": "not-run" }
  }
}
```

ZIP ingestion rejects absolute paths, `..` traversal, drive-qualified names,
symlinks, malformed archives, oversized members, oversized total extraction,
and too many members. Upload code is never imported or executed while it is
ingested.

## Docker

The repository-level `compose.yaml` starts the API and the static frontend.
The default Compose setup deliberately does **not** mount the Docker socket into
the API container.  Therefore generated test execution returns `unavailable` in
that deployment unless an operator supplies a separately designed execution
service.  This is safer than granting a web-facing API daemon access to the host
Docker socket.

For local execution with Docker installed, build the dedicated runner image and
run the API on the host:

```bash
docker build -t code-aid-runner:0.1.0 -f execution/Dockerfile .
CODE_AID_DOCKER_IMAGE=code-aid-runner:0.1.0 \
  ../.venv/bin/python -m uvicorn app.main:app --app-dir . --port 8000
```
