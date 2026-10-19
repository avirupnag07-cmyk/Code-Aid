# Code-Aid deployment readiness

Status: **ZIP-only, local-first release; no cloud deployment is required**.

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

`make docker-up` builds and starts the local container stack. API/frontend
images and Compose startup have been checked in Linux/arm64 containers on
Docker Desktop. Both published ports bind to loopback. The Compose API does
not receive the Docker socket, so isolated execution intentionally reports
unavailable in that deployment. For execution, use the host API with
`make runner-build` and `make run-backend`; an opt-in real Docker integration
test checks non-root, read-only, network-disabled execution:

```bash
CODE_AID_TEST_DOCKER=docker make test
```

The normal `make test` remains offline after dependencies are installed. Exact
host runtimes may differ; `make doctor` reports this, and Docker images use the
pins. Linux/amd64 has not been checked on this machine.

## Security and production gaps

- The API has no general user authentication or per-investigation
  authorization. Do not expose it as a public multi-user service.
- Native compiler checks are bounded but run in the backend service. They are
  not a substitute for the isolated execution runner.
- Remote execution of arbitrary non-Python project tests is not implemented.
- Isolated execution needs a running Docker daemon and the prebuilt runner
  image. No unsafe host execution fallback is provided.

## Publication and deployment status

The previous Vercel/Render deployments were deleted by the owner. Local
startup uses `/api` through Vite or Nginx, not a hosted backend. Existing
private environment files are preserved; remove stale hosted `VITE_API_URL`
overrides if necessary. Keep credentials out of the repository and image build
context. See README for exact local setup, run, test, and deployment commands.
