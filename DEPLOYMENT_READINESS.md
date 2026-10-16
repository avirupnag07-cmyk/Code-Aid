# Code-Aid deployment readiness

Status: **published to GitHub; deployment blocked pending compatible hosting
configuration**.

## Verified locally

- Frontend development preview: `http://127.0.0.1:5174/`
- Backend preview: `http://127.0.0.1:8001/`
- Health endpoint returned `status: ok`.
- Public Git import was exercised against the public Code-Aid repository at
  `main`, with `samples/simple-reproducible-bug` selected. The importer pinned
  commit `de290673fa5e48d23aaad4a6b80cfa6708bb7ff9` during this check.
- ZIP ingestion, source detection, native diagnostics, Python analysis,
  generated-test validation, report export, and patch verification were
  exercised through tests and API smoke checks.
- Diagnostic suite: **36 passed, 3 skipped**; full backend suite: **92 passed,
  3 skipped**; frontend suite: **5 passed**; production frontend build passed.
- GitHub OAuth status correctly reports `configured: false` in the current
  environment because no OAuth credentials are present.

## Language readiness in this environment

| Language | Detection | Native analysis | Test generation | Execution | Result |
| --- | --- | --- | --- | --- | --- |
| Python | ready | `ast` + Code-Aid rules | pytest template | Docker-only | validated |
| JavaScript | ready | Node syntax check | not configured | not configured | validated |
| TypeScript | ready | blocked: `tsc` missing | not configured | not configured | blocked |
| Java | ready | `javac` diagnostics | not configured | not configured | validated |
| C | ready | GCC diagnostics | not configured | not configured | validated |
| C++ | ready | G++ diagnostics | not configured | not configured | validated |
| Go | ready | blocked: detected wrapper not runnable in fixture environment | not configured | not configured | blocked |
| Rust | ready | blocked: complete `cargo` + `rustc` toolchain unavailable | not configured | not configured | blocked |

Detection is not counted as full language support. The Settings matrix and
`/api/languages` are the runtime source of truth.

## Required services and configuration

### Local or VM deployment

- FastAPI backend with Python 3.9.21 and the locked dependencies.
- React/Vite frontend served by Nginx or another static server.
- Git installed in the backend runtime for public/imported repository reads.
- SQLite and investigation storage on a persistent, access-controlled volume.
- A separate Docker runner and image for generated Python tests when execution
  is enabled.
- HTTPS and a stable `CODE_AID_OAUTH_COOKIE_SECRET` for GitHub OAuth.
- GitHub OAuth App credentials, a registered callback URL, and a deliberate
  review of the broad `repo` scope limitation.

### Compose

`docker compose up --build` is the intended local container command. It was not
executed in this environment because Docker is not installed. The Compose API
does not receive the Docker socket, so isolated execution is expected to report
unavailable in that deployment.

## Security and production gaps

- The API has no general user authentication or per-investigation
  authorization. Do not expose it as a public multi-user service.
- OAuth sessions are process-local and expire; a multi-worker deployment needs a
  shared encrypted session store and explicit token revocation/expiry handling.
- The OAuth App `repo` scope is broader than least privilege. A GitHub App with
  installation-level read permissions is preferred for production.
- Native compiler checks are bounded but run in the backend service. They are
  not a substitute for the isolated execution runner.
- Remote execution of arbitrary non-Python project tests is not implemented.
- Docker image build, Compose startup, and isolated execution are blocked until
  Docker is installed and a daemon is available.

## Publication and deployment status

The approved commits were pushed to:

```text
https://github.com/avirupnag07-cmyk/Code-Aid.git
```

Published `main` commit:

```text
af4a052bb8b0b5a063f98eacf56cabd699b5fc8c
```

No deployment URL exists yet. Deployment is blocked because this environment
has no Docker daemon, hosting-provider CLI, provider configuration, or supplied
hosting credentials. A static-only host would not be compatible with Git
imports, SQLite persistence, or isolated execution.
