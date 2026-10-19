# Reproduce Code-Aid on Linux

This guide starts from a clean checkout. No Vercel/Render deployment, API key,
external database, global Python package, or global npm package is needed.
The application code is identical for both sample outcomes; only the uploaded
fixture changes.

## Choose a mode

| Mode | Prerequisites | What can be judged |
| --- | --- | --- |
| Host API + Vite + Docker runner (recommended) | Git, Bash, Python 3.9.21 with venv/pip, Node 22.14.0 with npm 10+, Docker Engine | Full UI, analysis, real failed/passed Python execution |
| Docker Compose | Git, Bash, Docker Engine and Compose v2.20+ | Containerized UI, analysis, persistence; generated-test execution is intentionally unavailable |

Have the Linux administrator provision these prerequisites using the official
runtime/Docker installation instructions. Docker must be usable by your current
user without prefixing project commands with `sudo`. Use rootless Docker or an
administrator-approved setup; Docker group membership grants powerful host
access. Never expose an unauthenticated Docker TCP endpoint.

GNU Make is optional for the direct commands below. Version pins live in
`backend/.python-version`, `frontend/.nvmrc`, and the Dockerfiles. Initial setup
needs internet to obtain locked dependencies/base images. Tests are offline
after installation. Disk space is needed for npm dependencies and Docker images.

## 1. Clone and check prerequisites

```bash
git clone https://github.com/avirupnag07-cmyk/Code-Aid.git
cd Code-Aid
git rev-parse HEAD
python3.9 --version
node --version
npm --version
docker info
```

Use Python **3.9.21** and Node **22.14.0** for the pinned host setup. If those
runtimes are not installed, provision them first, or choose Compose below for
an exact-runtime container build. Docker Engine must already be running; its
startup procedure depends on the Linux distribution/rootless configuration.
`open -a Docker` is a macOS command and must not be used on Linux.
For Compose-only setup, clone the repository and check `docker info`, then skip
the host Python/Node steps and use the Docker-only deployment section.

All following commands run from the directory containing `Makefile`,
`backend/`, `frontend/`, and `compose.yaml`. Keep this directory available while
the host backend is running because it stores the local investigations here.

## 2. Install and build the isolated runner

```bash
python3.9 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock
npm --prefix frontend ci
docker build --file execution/Dockerfile --tag code-aid-runner:0.1.0 .
.venv/bin/python scripts/doctor.py
```

This installs packages only in `.venv/` and `frontend/node_modules/`. The
complete lockfiles are `backend/requirements.lock` and
`frontend/package-lock.json`. Do not substitute unpinned `pip install` or
`npm install` commands. The doctor reports runtime deviations and missing
dependencies/daemon access without exposing private environment contents.

No environment file is required for the defaults. If you need overrides, copy
values from `.env.example` into a private root `.env` without overwriting
existing settings. Vite uses `frontend/.env*` separately. Remove old hosted
`VITE_API_URL` values; the command below explicitly selects local `/api`.

## 3. Start the full local application

Terminal 1, from the repository root:

```bash
CODE_AID_DOCKER_IMAGE=code-aid-runner:0.1.0 .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Terminal 2, from the same repository root:

```bash
VITE_API_URL=/api npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

- Website: http://127.0.0.1:5173
- Health: http://127.0.0.1:8000/api/health
- Interactive API: http://127.0.0.1:8000/docs

Keep both terminals open. Stop with `Ctrl-C`; SQLite/source data remain in
`backend/data/`. If a port is occupied, stop the old instance rather than
starting two copies. Do not expose this unauthenticated local tool publicly.

## 4. Judge the failed and passed ZIPs

In the website, create two separate investigations with these uploads:

| ZIP to upload | Expected result after Run tests |
| --- | --- |
| `test-fixtures/broken-python-project.zip` | One failed assertion execution: calculator raises a real `TypeError`; exit 1 |
| `test-fixtures/corrected-python-project.zip` | One passed expected-output test; exit 0; no skips |

Both generated tests call `total_with_tax(100.0, "8")` and require `108.0`.
The corrected implementation converts the rate to a number and applies an 8%
tax. Its bundled traceback is explicitly **historical regression context**,
not a current error. Investigation creation alone is not an execution result:
open the generated-test section and request a run.

For a headless verification of the exact same ZIPs, without a running API:

```bash
PYTHONPATH=backend .venv/bin/python test-fixtures/check_zip_cases.py
.venv/bin/python test-fixtures/build_corrected_zip.py --check
```

The first command exits successfully only if both actual Docker outcomes match.
An unavailable runtime, import/collection error, or skipped generated test does
not count as success. The second checks that the corrected archive matches its
reproducible source build. More details: [fixture README](test-fixtures/README.md).

## 5. Run the offline test suite and production build

After dependencies are installed, the single repository check command is:

```bash
make test
```

If Make is not available, run the equivalent commands directly:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

The last command checks TypeScript and creates `frontend/dist/`. Optional
language toolchains are reported unavailable/skipped, never silently installed
or counted as supported. Python is the only current isolated execution target.

For additional real Docker regression tests, with the image already built:

```bash
CODE_AID_TEST_DOCKER=docker PYTHONPATH=backend .venv/bin/python -m pytest -q backend/tests
```

## Alternative: Docker-only local deployment

Only Git, Docker Engine, and the Compose plugin are needed for this mode. After
cloning the repository, run:

```bash
docker compose version
docker compose up --build --detach --wait
docker compose ps
```

Open http://127.0.0.1:5173. The images install their own system/runtime
dependencies; the backend uses Python 3.9.21 and the frontend build uses Node
22.14.0. Nginx serves the SPA and proxies `/api` internally to FastAPI.
Persistent SQLite/source data live in a named volume.

**This does not provide Docker-generated test execution.** The API container
does not receive the host Docker socket. Use the host API setup above to judge
the failed/passed execution cases. Do not add a socket mount as a shortcut.

If the development servers already occupy ports 8000 and 5173:

```bash
CODE_AID_API_PORT=18000 CODE_AID_FRONTEND_PORT=15173 docker compose up --build --detach --wait
```

Then open http://127.0.0.1:15173. All published ports bind to loopback. To stop
without deleting persisted investigations:

```bash
docker compose down
```

For an access-controlled Linux VM, use this same deployment and a trusted SSH
tunnel to access its loopback ports. No public hosting provider is required.
Back up the named volume before replacing a machine. Never use
`docker compose down -v` unless you intend to delete the database and sources.

### Offline checks with pinned Linux containers

If host Python/Node are unavailable, prepare these check images while online:

```bash
docker build --tag code-aid-api:0.1.0 .
docker build --target build --tag code-aid-frontend-check:0.1.0 --file frontend/Dockerfile .
```

Then run the installed suites with networking disabled. The read-only mounts
provide test-only fixtures and runtime pins, not a Docker socket:

```bash
docker run --rm --network none --workdir /app --env PYTHONPATH=/app/backend --volume "$PWD/scripts:/app/scripts:ro" --volume "$PWD/frontend/.nvmrc:/app/frontend/.nvmrc:ro" --volume "$PWD/test-fixtures:/app/test-fixtures:ro" code-aid-api:0.1.0 python -m pytest -q -p no:cacheprovider backend/tests
docker run --rm --network none code-aid-frontend-check:0.1.0 npm test -- --run
```

These unit/API checks do not run Docker-in-Docker. Native toolchain and opt-in
Docker tests can be skipped in the minimal backend image. Use the host-mode
ZIP check above for evidence of actual uploaded-code execution.

## Troubleshooting and verification limits

- **`unavailable`:** check `docker info`, build `code-aid-runner:0.1.0`, and
  ensure the backend is on the host with `docker` on its process PATH.
- **Broken ZIP says `failed`:** expected; inspect the calculator TypeError.
- **Corrected ZIP still fails:** create a new investigation with the corrected
  archive, not a rerun of the original broken upload. Check stale backend
  instances and restart the host API after pulling changes.
- **`ModuleNotFoundError`:** use the current checkout; wrapper/`src` import-root
  support is included. Arbitrary dependencies are not installed into the runner.
- **Historical findings in the passed case:** analysis still uses the original
  report. The execution receipt is the evidence that the regression test passes.

The maintained fixtures are small deterministic examples, not proof of universal
bug diagnosis. Containers and real ZIP cases have been checked on Linux/arm64
under Docker Desktop; a native Linux/amd64 host has not been available in this
environment. Record `git rev-parse HEAD` and your runtime versions when judging.
