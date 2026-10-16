# Code-Aid deployment readiness

Status: **ZIP-only release; deployment still requires compatible hosting
configuration**.

## Verified locally

- ZIP ingestion, source detection, native diagnostics, Python analysis,
  generated-test validation, report export, and patch verification are covered
  by the test suite.
- A deliberately broken, credential-free ZIP smoke-test fixture is committed at
  `test-fixtures/broken-python-project.zip`.
- The web UI accepts ZIP uploads only. Git repository import and GitHub OAuth
  code and settings have been removed from this release.

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
- SQLite and investigation storage on a persistent, access-controlled volume.
- A separate Docker runner and image for generated Python tests when execution
  is enabled.

### Compose

`docker compose up --build` is the intended local container command. It was not
executed in this environment because Docker is not installed. The Compose API
does not receive the Docker socket, so isolated execution is expected to report
unavailable in that deployment.

## Security and production gaps

- The API has no general user authentication or per-investigation
  authorization. Do not expose it as a public multi-user service.
- Native compiler checks are bounded but run in the backend service. They are
  not a substitute for the isolated execution runner.
- Remote execution of arbitrary non-Python project tests is not implemented.
- Docker image build, Compose startup, and isolated execution are blocked until
  Docker is installed and a daemon is available.

## Publication and deployment status

No deployment URL is recorded in this repository. Deployment requires a
backend host with persistent storage for SQLite/source data and a static
frontend host configured with the backend API prefix. Keep provider URLs and
credentials in the deployment dashboard, not in this repository.
