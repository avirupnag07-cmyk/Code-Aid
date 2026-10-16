# Changelog

All notable changes to Code-Aid are recorded here.

## [Unreleased] - 2026-10-16

### Added

- ZIP-only project intake for the initial web workflow; Git repository import
  and GitHub authentication are intentionally disabled.
- Deliberately broken per-language fixtures and native diagnostic validation
  tests.
- Shared language adapter registry with live `/api/languages` support matrix.
- Bounded native syntax/compiler diagnostics for Python, JavaScript,
  TypeScript, Java, C, C++, Go, and Rust when their toolchains are installed.
- Language-adapter fixtures and explicit non-Python test-generation gaps.
- Native diagnostic display in the source evidence workspace.
- Security model documentation.

### Changed

- Landing page, docs, and workspace copy now distinguish analysis availability
  from language-native test generation and execution.

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
