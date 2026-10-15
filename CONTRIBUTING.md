# Contributing to Code-Aid

Thank you for improving Code-Aid. The project is intentionally small and
local-first so a contributor can understand the complete investigation flow.

## Development setup

```bash
make setup
make test
```

Run the API and Vite frontend with `make run-backend` and `make run-frontend`.
The API is a Python 3.9.21 project and the interface is a Node 22.14.0
project. Do not install either dependency set globally.

## Working agreements

- Keep facts, findings, hypotheses, generated tests, execution receipts, and
  verification results as separate concepts in API responses and UI copy.
- Do not execute uploaded project code in the API process.
- Do not add a local fallback for the Docker runner when Docker is unavailable.
- Treat archive names, file paths, metadata, and traceback text as untrusted.
- Prefer deterministic, evidence-linked behavior over invented explanations.
- Add or update tests for every engine or API behavior change.
- Keep user-facing claims honest about what was and was not verified.
- Avoid unrelated formatting churn and machine-specific paths.

## Pull request checklist

- [ ] `make test` passes.
- [ ] Changed API behavior has an API test.
- [ ] Changed UI behavior has a critical workflow test or a documented manual
      smoke check.
- [ ] Security-sensitive changes include boundary tests.
- [ ] README or docs reflect new commands, limits, and known limitations.
- [ ] No secrets, generated databases, dependency directories, or build output
      are included.

## Commit style

Use concise conventional prefixes such as `feat:`, `fix:`, `test:`, `docs:`,
`refactor:`, or `chore:`. Keep each commit focused and runnable.
