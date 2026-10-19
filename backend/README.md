# Code-Aid backend

The backend is a Python 3.9-compatible FastAPI service for safe, deterministic
bug investigations. It parses uploaded source as data, detects supported
languages, runs bounded native syntax/compiler checks, performs Python AST
analysis where applicable, ranks reproducible hypotheses, generates pytest
source without executing it on the host, and persists every result in SQLite.

## Setup

Run all commands below from the **repository root**, containing `backend/` and
`frontend/`. Use Python **3.9.21**, pinned in `backend/.python-version`:

```bash
python3.9 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
```

`backend/requirements.lock` pins direct and transitive backend/test
dependencies; `requirements.txt` is not the complete lock. No model provider or
external API is required. Judges should start with
[the Linux reproduction guide](../README.linux.md).

## Run

From the repository root:

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

The service defaults to the repository's `samples/` directory and stores SQLite
data and ingested projects under `backend/data/`. Root `.env` overrides are
optional; exported environment variables take precedence. `backend/.env` is
not loaded. Never commit private environment files.

## Test

The repository-wide offline check (after root setup) is:

```bash
make test
```

Without Make, run backend tests directly:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests
```

Tests use only the pinned local dependencies and do not require Docker. Docker
is intentionally optional for the run-tests endpoint; without it the endpoint
returns an `unavailable` result and never executes project code on the host.

## API contract

The canonical routes are under `/api`; identical root aliases are provided for
simple local React proxy setups. FastAPI publishes the interactive contract at
http://127.0.0.1:8000/docs and the OpenAPI document at
http://127.0.0.1:8000/openapi.json. The `/api` prefix is for API routes, not the
documentation endpoints.

### System and samples

| Method | Route | Behavior |
| --- | --- | --- |
| `GET` | `/api/health` | Returns service/version/database health. |
| `GET` | `/api/languages` | Returns the live language adapter/toolchain matrix. |
| `GET` | `/api/language-support` | Compatibility alias for the language matrix. |
| `GET` | `/api/samples` | Lists safe bundled sample choices and their metadata/traceback. |
| `GET` | `/api/samples/{sample_id}` | Returns one sample descriptor. |

### Investigations

| Method | Route | Body / result |
| --- | --- | --- |
| `GET` | `/api/investigations?limit=100&offset=0` | Lists persisted summaries. |
| `POST` | `/api/investigations` | Accepts multipart ZIP upload for the web workflow. Bundled sample creation remains available to local regression tests. |
| `GET` | `/api/investigations/{id}` | Returns the full persisted investigation. |
| `DELETE` | `/api/investigations/{id}` | Deletes the record and its private ingested project directory. |
| `POST` | `/api/investigations/{id}/run-tests` | Optional JSON `{ "timeout_seconds": 20 }`; executes generated tests only in Docker and appends an execution result. |
| `POST` | `/api/investigations/{id}/verify` | JSON `{ "file_path": "module.py", "content": "..." }` (or `path`) checks a proposed change without mutating the stored project and, when Docker is available, compares baseline and staged-patch test runs. |
| `GET` | `/api/investigations/{id}/report` | Downloads a `text/markdown` report. |

Creation returns an object with these deliberately separate result sections:

```json
{
  "id": "uuid",
  "source": { "source_type": "upload", "original_filename": "project.zip", "traceback": "..." },
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
  .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

In another terminal, verify both public ZIP cases using that image:

```bash
PYTHONPATH=backend .venv/bin/python test-fixtures/check_zip_cases.py
```

Expected results are `failed` for the deliberately broken calculator and
`passed` for the corrected calculator. See [fixture instructions](../test-fixtures/README.md).
