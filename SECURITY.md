# Security model

Code-Aid is a local-first developer tool. It is not an authenticated,
multi-tenant service and must not be exposed to an untrusted network without an
additional authentication, authorization, rate-limiting, and data-isolation
boundary.

## Implemented controls

- ZIP uploads are bounded by compressed size, member count, extracted bytes,
  per-member bytes, and source-file bytes.
- Absolute paths, traversal, drive-qualified names, NUL bytes, and symlinks are
  rejected during ingestion.
- Uploaded source is copied and parsed as data. The API does not import project
  modules or run startup scripts during analysis.
- Native language adapters use argument arrays, bounded output, short timeouts,
  and parser/compiler check modes. They do not install dependencies.
- Generated tests are eligible for execution only when validation succeeds and
  the Docker runner is available.
- The runner requests no network, no privileges, dropped capabilities,
  `no-new-privileges`, CPU/memory/PID limits, read-only source mounts, and a
  bounded timeout.
- Patch verification is non-mutating and stages proposed files separately.
- Reports and investigation records are stored locally; deletion removes the
  persisted record and its private source copy when it remains inside the
  configured storage root.

## Remaining risks

- The Docker daemon and host kernel remain part of the execution trust boundary.
- The Compose web service intentionally has no Docker socket, so execution is
  unavailable there by design. Do not mount the socket into the API as a
  convenience workaround.
- Local SQLite and source storage may contain sensitive code and should be
  protected with filesystem permissions and backups appropriate to the machine.
- There is no authentication or per-user authorization in this release.
- Toolchains are invoked from the server environment. Keep compiler/runtime
  installations patched and do not add unreviewed tools to the execution PATH.
- Dependency installation, archive parsing, and compiler behavior still depend
  on their upstream supply chains; Code-Aid is not a security certification.

## Reporting a vulnerability

Please do not publish a working exploit in an issue. Contact the repository
maintainer privately with a minimal reproduction, affected version or commit,
impact, and any suggested mitigation. Do not include secrets or private source
code in the report.
