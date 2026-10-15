# Changelog

All notable changes to Code-Aid are recorded here.

## [0.1.0] - 2026-10-15

### Added

- Local-first FastAPI and React/Vite application.
- Secure Python ZIP ingestion and traceback parsing.
- Evidence-backed AST findings and deterministic hypotheses.
- pytest template generation and validation.
- Docker-only test runner with explicit unavailable and timeout receipts.
- Non-mutating proposed-file syntax/diff verification.
- SQLite persistence and Markdown diagnostic reports.
- Three bundled sample investigations.
- Responsive landing page, workspace, new-investigation form, results tabs,
  settings, documentation, and security copy.
- Backend and frontend automated tests, pinned dependencies, and Docker
  Compose configuration.

### Known gaps

- Patch verification is limited to the generated tests; it does not run a full
  project suite or guarantee that untested regressions are absent.
- No authentication, remote model integration, or PDF report export.
