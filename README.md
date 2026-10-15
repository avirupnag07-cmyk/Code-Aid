# Code-Aid

> **From bug reports to reproducible fixes.**

Code-Aid is a local-first Bug Reproduction Engineer for Python projects. It
turns an error report into a bounded investigation: source is inspected without
execution, traceback frames are linked to AST findings, probable causes remain
explicitly provisional, pytest cases are generated and validated, and every
execution or patch check is recorded as evidence.

## Quick start

### Prerequisites

- Python **3.9.21** (the backend runtime is pinned in `backend/.python-version`)
- Node.js **22.14.0** (the frontend runtime is pinned in `frontend/.nvmrc`)
- npm 10+ (or a compatible npm release)
- Docker is optional for local analysis, but required to execute generated tests

### Install

```bash
git clone <your-local-copy>
cd Code-Aid
make setup
```

`make setup` creates the project-local `.venv`, installs the pinned backend
lockfile, and installs the pinned frontend lockfile. No global package install
is required.

### Run locally

Start the API in one terminal:

```bash
make run-backend
```

Start the interface in another:

```bash
make run-frontend
```

Open **http://localhost:5173**. The API health endpoint and interactive API
contract are at **http://localhost:8000/api/health** and
**http://localhost:8000/docs**.

### Run the checks

```bash
make test
```

This runs the backend unit/API/security suite and the frontend critical-flow
test suite offline using already-installed project dependencies.

### Start with Docker Compose

```bash
docker compose up --build
```

Open **http://localhost:5173**. Compose persists SQLite data in the named
`code_aid_data` volume. The Compose API does **not** receive the Docker socket;
test execution therefore reports `unavailable` rather than executing uploaded
code unsafely. See [Test execution](#test-execution-architecture) for the
separate local runner setup.

### Run a bundled sample investigation

The simplest path is **Open workspace → New investigation → Checkout tax
calculator**. The same flow is available through the API:

```bash
curl -sS -X POST http://localhost:8000/api/investigations \
  -H 'content-type: application/json' \
  -d '{"title":"Checkout tax sample","sample_id":"simple-reproducible-bug"}'
```

The response contains an investigation identifier and separate `facts`,
`findings`, `hypotheses`, `generated_tests`, `execution_results`, and
`verification` sections.

## Detailed documentation

### Product overview

Code-Aid is designed for the first investigation pass after a bug is reported:

1. Capture the report, traceback, reproduction notes, and project.
2. Ingest the project as untrusted data and inventory its source.
3. Parse the exception and resolve traceback frames where possible.
4. Run deterministic AST rules and attach line-level evidence.
5. Rank root-cause hypotheses without presenting them as facts.
6. Generate a focused pytest template and syntactically validate it.
7. Request a Docker-only test run when an isolated runtime is available.
8. Check a proposed source change without mutating the original project.
9. Export a Markdown report that records observations and limitations.

The application intentionally does not require an external model provider or
paid API key. Optional language-model assistance is an extension point, not a
hidden dependency in the core workflow.

### Features

- Public landing page with a truthful, non-running product preview.
- Responsive workspace dashboard backed by real SQLite records.
- New-investigation form with bundled samples and ZIP upload.
- Archive path-traversal, symlink, member-count, and byte-budget protection.
- Python traceback parsing for common exception families.
- AST-based findings with source file, line, snippet, and rule evidence.
- Deterministic ranked hypotheses with stated confidence limitations.
- Validated pytest generation from safe sample metadata.
- Docker-only runner with explicit unavailable and timeout states.
- Non-mutating proposed-file syntax and diff verification.
- Downloadable Markdown diagnostic reports.
- Investigation deletion with confirmation and cleanup.
- Documentation, security notes, sample projects, and automated tests.

### Screenshots

Screenshots are not included in this source-only build. Run the local frontend
and capture the landing page, empty workspace, new-investigation form, and
results workspace if screenshots are needed for a release document.

### Architecture overview

```text
Browser / React + TypeScript + Vite
              │ JSON / multipart HTTP
              ▼
FastAPI routes + Pydantic validation
              │
              ├── SQLite repository (records and JSON results)
              ├── controlled investigation storage (source copies)
              └── deterministic engine modules
                    ├── ingestion
                    ├── traceback parser
                    ├── AST analyzer
                    ├── hypothesis ranking
                    ├── test generation / validation
                    ├── Docker-only runner
                    ├── patch verification
                    └── Markdown report renderer
```

The engine modules do not import project code during analysis. Storage is local
and does not require authentication for the MVP. The service exposes the same
routes under `/api` and root aliases for simple local development.

### Project directory structure

```text
backend/
  app/
    api/routes.py          # HTTP boundary and workflow orchestration
    config.py              # environment-backed limits and paths
    db.py                  # SQLite repository
    engine/
      ingestion.py         # sample/ZIP intake and archive safety
      traceback_parser.py  # exception/frame extraction
      analyzer.py          # source AST rules
      ranking.py           # deterministic hypotheses
      test_generation.py   # pytest template and validation
      runner.py             # Docker-only execution
      patch_verifier.py    # non-mutating path/syntax/diff checks
      report.py             # Markdown export
    schemas.py
    main.py
  tests/
samples/
  simple-reproducible-bug/
  unexpected-type-bug/
  regression-after-fix-bug/
frontend/
  src/components/          # shell and reusable diagnostic components
  src/pages/               # landing, workspace, docs, settings
  src/lib/                 # API contract and domain types
  src/styles/              # design tokens and responsive UI
execution/Dockerfile       # pinned pytest runner image
compose.yaml
Makefile
```

### Technology stack and rationale

- **Python 3.9.21:** matches the portable baseline for supported sample code;
  the application avoids newer-only language syntax.
- **FastAPI + Pydantic:** typed HTTP validation and an automatically published
  OpenAPI contract without a large framework footprint.
- **SQLite:** durable local-first storage with no separate service.
- **Python `ast`:** standard-library parsing of source without importing it.
- **React + TypeScript + Vite:** fast, typed UI development and a small static
  production bundle.
- **pytest:** familiar generated-test format and the project test runner.
- **Docker:** a separate process/filesystem/network boundary for untrusted test
  execution. A runtime is optional, and the API never silently executes locally.

### Installation instructions

The supported developer path is:

```bash
make setup
```

If you prefer manual steps:

```bash
python3.9 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
npm --prefix frontend ci
```

The lockfiles are `backend/requirements.lock` and
`frontend/package-lock.json`. Runtime dependencies are installed only into the
project virtual environment and `frontend/node_modules`.

### Environment variables

Copy `.env.example` to `.env` for the common local overrides. The backend also
supports the variables in `backend/.env.example`; it reads environment values
directly rather than using a secret manager in this local MVP.

| Variable | Default | Purpose |
| --- | --- | --- |
| `CODE_AID_DATABASE` | `backend/data/code_aid.sqlite3` | SQLite file |
| `CODE_AID_STORAGE` | `backend/data/investigations` | private source copies |
| `CODE_AID_SAMPLES` | `samples` | bundled sample directory |
| `CODE_AID_MAX_UPLOAD_BYTES` | `10485760` | compressed upload limit |
| `CODE_AID_MAX_ARCHIVE_MEMBERS` | `200` | ZIP member limit |
| `CODE_AID_MAX_ARCHIVE_BYTES` | `26214400` | total extracted-byte limit |
| `CODE_AID_MAX_ARCHIVE_MEMBER_BYTES` | `5242880` | per-member limit |
| `CODE_AID_MAX_SOURCE_FILE_BYTES` | `524288` | source/patch limit |
| `CODE_AID_RUN_TIMEOUT_SECONDS` | `20` | default isolated run timeout |
| `CODE_AID_DOCKER_IMAGE` | `python:3.9-slim` | execution image name |
| `CODE_AID_ALLOWED_ORIGINS` | `*` | comma-separated CORS origins |

Do not put tokens, credentials, source dumps, or private logs into `.env` or
committed files.

### Backend configuration

For a host process started from the repository root:

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000
```

For a Docker Compose API, paths are configured inside the image and persistent
data is mounted at `/app/backend/data`. Keep the local API bound to loopback
when you are not intentionally using the Compose network.

### Frontend configuration

The Vite development server proxies `/api` to `http://127.0.0.1:8000`. To use a
different API origin, set `VITE_API_URL` before building the frontend:

```bash
VITE_API_URL=http://127.0.0.1:8000/api npm --prefix frontend run build
```

The production container uses Nginx to serve the SPA and proxies `/api/` to the
Compose backend service.

### Database setup

SQLite tables are created automatically at startup. No migration command is
needed for the initial schema. The investigation row stores source metadata,
JSON engine results, and a path to the private copied project. Deleting an
investigation deletes both the row and its project directory when it remains
inside the configured storage root.

The database is local application state, not a multi-user server. Back it up by
stopping the API and copying the SQLite file together with the investigation
storage directory.

### API documentation

The canonical API prefix is `/api`:

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/health` | health and version |
| GET | `/api/samples` | bundled sample catalog |
| GET | `/api/samples/{sample_id}` | sample metadata and traceback |
| GET | `/api/investigations` | stored summaries |
| POST | `/api/investigations` | JSON, form, or ZIP-based analysis |
| GET | `/api/investigations/{id}` | full result record |
| DELETE | `/api/investigations/{id}` | delete record and stored source |
| POST | `/api/investigations/{id}/run-tests` | Docker-only generated-test run |
| POST | `/api/investigations/{id}/verify` | non-mutating proposed file check |
| GET | `/api/investigations/{id}/report` | Markdown download |

`POST /api/investigations` accepts `sample_id` or a `.zip` field named
`archive`, `file`, `zip_file`, or `project`; it rejects choosing both. JSON can
carry a base64 ZIP as `archive_base64`. Optional report intake fields are
`bug_description`, `reproduction_steps`, `expected_behavior`,
`actual_behavior`, and `environment`.

FastAPI publishes the live contract at `/docs` and `/openapi.json` when the
backend is running.

### Analysis pipeline

#### 1. Project ingestion

The ZIP reader validates every member name before extraction. It rejects
absolute names, Windows drive-qualified names, `..` components, NUL bytes,
symlinks, malformed archives, too many members, oversized members, and total
extraction beyond the configured budget. Sample directories are copied through
the same symlink and source-size checks. `.git`, bytecode, virtualenv, and build
directories are not needed by the analyzer; source inventory only includes
regular files present in the ingested project. No source module is imported at
this stage.

#### 2. Traceback parsing

The parser supports `AttributeError`, `TypeError`, `NameError`, `ImportError`,
`ModuleNotFoundError`, `KeyError`, `IndexError`, `ValueError`,
`FileNotFoundError`, `ZeroDivisionError`, and `AssertionError`, plus a few
common Python families retained for compatibility. It extracts the exception
type, message, final line, and each `File ..., line ..., in ...` frame. It also
handles pytest-style `E ` prefixes and reports malformed input as a validation
error.

#### 3. Static analysis

The analyzer parses Python source with `ast.parse`. Current rules cover
traceback-linked attribute access, mapping lookup, sequence indexing, numeric
conversion, mixed literal operations, broad exception handlers, syntax errors,
and missing traceback files. Findings contain a rule id, severity, explanation,
and evidence with relative path, line, and snippet. These rules are useful
signals, not a complete Python linter or proof of root cause.

#### 4. Hypotheses and generated tests

The ranking engine combines the exception family with matching static rules and
sample metadata. Scores are deterministic and shown as confidence signals;
they are never labeled “confirmed” by the interface. Generated test templates
only use safe module/function identifiers and Python-literal arguments from
bundled metadata. The source is AST-parsed, checked for a `pytest` import and a
`test_` function, then persisted with its validation status.

### Test-execution architecture

The API process does not import or run the project under investigation. The
runner prepares generated test files in a temporary directory and, when Docker
is available, invokes a disposable container with:

- `--network none`
- no privileged mode
- all Linux capabilities dropped
- `no-new-privileges`
- explicit CPU, memory, and PID limits
- a read-only source mount and read-only generated-test mount
- a no-exec, no-suid, no-dev temporary filesystem
- a bounded subprocess timeout
- bounded captured output
- no host Docker socket in the application container

Build the dedicated runner image when you want host-local test execution:

```bash
docker build -t code-aid-runner:0.1.0 -f execution/Dockerfile .
CODE_AID_DOCKER_IMAGE=code-aid-runner:0.1.0 \
  .venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8000
```

This still relies on the Docker daemon and its host policy. The Compose
deployment intentionally leaves execution unavailable rather than mounting the
Docker socket into a network-facing API. A future production deployment should
use a separate execution service with an explicit authorization boundary.

The current generated reproduction test normally asserts that the reported
exception is raised. A passing generated test means the reported behavior was
reproduced; it does not prove a fix. Patch verification currently performs safe
path checks, Python syntax checks, and a unified diff without mutating the
stored project. It does not silently claim that a proposed patch changed runtime
behavior.

### Security model

Code-Aid is a local developer tool, not a claim of complete isolation or a
security certification.

Implemented controls:

- input validation through typed API boundaries;
- configurable upload, archive, source, traceback, and output limits;
- path traversal and symlink rejection;
- no shell command construction from uploaded values;
- no project imports or execution during API analysis;
- no unsafe local fallback when Docker is missing;
- safe relative paths for generated tests and proposed patches;
- non-mutating patch verification;
- cleanup of temporary directories and deleted investigations;
- no credentials in the repository and an `.env.example` with placeholders.

Remaining risks and operator responsibilities:

- the Docker daemon, Linux kernel, and container runtime must be patched and
  configured appropriately;
- local storage contains source code and should be protected by filesystem
  permissions;
- the unauthenticated API is not suitable for exposure to an untrusted network;
- a malicious project may still target parser or runtime implementation bugs;
- dependency installation and Docker image supply chains require review;
- metadata may contain sensitive text supplied by the developer.

### Supported errors

The initial user-facing focus is `AttributeError`, `TypeError`, `NameError`,
`ImportError`, `ModuleNotFoundError`, `KeyError`, `IndexError`, `ValueError`,
`FileNotFoundError`, `ZeroDivisionError`, and `AssertionError`. The parser is
also tolerant of a few additional Python exception names, but static rules and
generated tests are not equally specialized for every family.

### Known limitations

- Only Python source projects are analyzed in this release.
- The AST rule set is intentionally small and deterministic; it is not a full
  type checker, control-flow engine, or universal bug detector.
- Generated tests need a safe sample `test_spec` to call a known function. When
  that metadata is absent, Code-Aid produces a clearly skipped template.
- Docker is optional. Without a daemon and a prebuilt runner image, execution
  is explicitly unavailable.
- Patch verification does not yet run a patched copy and baseline comparison;
  it proves only that the proposed file is safe to inspect, parses as Python,
  and differs from the current file.
- There is no authentication, team sharing, remote model provider, or PDF
  export in the local MVP.
- Compose persists the database, but source execution remains unavailable by
  design unless a separately reviewed executor is deployed.

### Testing instructions

Run the one repository check command:

```bash
make test
```

The backend suite covers parser classification and malformed inputs, archive
limits and traversal, static findings, deterministic ranking, generated-test
validation, SQLite/API persistence, report generation, patch safety, and
runner unavailable/timeout handling. The frontend suite covers the critical
landing-page promise and workspace route affordance. Tests do not require
Docker; Docker-dependent execution is tested through safe unavailable and
timeout branches because Docker is optional.

For a manual smoke test:

```bash
make run-backend
# in another terminal
make run-frontend
```

Select all three bundled samples from `/app/new`, inspect their findings, open
the generated-test tab, request a run, and download a report. In an environment
without Docker, confirm that the receipt says `unavailable` and that no project
code was executed in the API process.

### Troubleshooting

**The frontend says the API is unavailable.** Ensure the backend is running on
port 8000, or set `VITE_API_URL` to the API prefix before starting/building the
frontend. The Vite dev proxy is `/api` → `http://127.0.0.1:8000`.

**An upload is rejected.** Upload a regular `.zip` file under the configured
size/member limits. Archives with absolute paths, `..`, symlinks, or no
`traceback.txt`/metadata traceback will fail safely.

**Tests say unavailable.** Build `execution/Dockerfile`, set
`CODE_AID_DOCKER_IMAGE=code-aid-runner:0.1.0`, and run the API on the host with
Docker available. Do not mount the Docker socket into the public Compose API as
a workaround.

**The database has stale records.** Stop the API and remove `backend/data/` or
the Compose `code_aid_data` volume only when you intend to discard local
investigations.

### Docker instructions

The root `compose.yaml` builds two services:

- `backend`: FastAPI, bundled samples, and a named SQLite/data volume;
- `frontend`: Vite production build served by Nginx with SPA fallback and an
  `/api/` reverse proxy.

Build and run with:

```bash
docker compose up --build
```

Stop while retaining the named data volume with `Ctrl-C` followed by
`docker compose down`. `docker compose down -v` removes persisted local data.
The image build does not bake secrets. Health checks call the local API and
frontend endpoints only.

### Development contribution guidelines

Read [CONTRIBUTING.md](CONTRIBUTING.md) before editing. Keep engine modules
deterministic and side-effect-conscious, add a regression test for behavior
changes, update the API/documentation when contracts change, and run `make
test` before committing. Never add credentials, source fixtures containing
secrets, or machine-specific absolute paths.

### License

Code-Aid is released under the MIT License; see [LICENSE](LICENSE).
