# Judge fixtures: failed and passed Python investigations

These public, credential-free ZIPs let judges compare both outcomes without
editing Code-Aid's application code. See [Linux setup](../README.linux.md) first.

| Archive | Source behavior | Expected generated-test receipt |
| --- | --- | --- |
| [broken-python-project.zip](broken-python-project.zip) | Adds a float and strings | `failed`, pytest exit 1, one calculator TypeError |
| [corrected-python-project.zip](corrected-python-project.zip) | Applies a numeric percentage tax | `passed`, pytest exit 0, one passed test |

Both metadata specifications use `calculator.total_with_tax(100.0, "8")` and
expected value `108.0`. This is an **expected-output** test, not a test that
passes merely by reproducing an exception. Neither result should be skipped or
fail during import/collection.

## Browser checklist

1. Start the host API and Vite frontend using the Linux guide. Start Docker and
   build `code-aid-runner:0.1.0` first. Compose alone intentionally cannot execute
   generated tests.
2. Open http://127.0.0.1:5173/app/new and upload the broken ZIP.
3. Open generated tests and run them. Confirm `failed` and a calculator TypeError.
4. Create a **new investigation** with the corrected ZIP. Run its generated test.
5. Confirm `passed`, `1 passed`, and exit code 0. Download reports if required.

The corrected ZIP includes the **historical** traceback of the original bug so
the existing bug-report workflow can generate the same regression test. That
report is not a fresh exception from corrected code. Static findings or
hypotheses may still discuss the historical report; use the execution receipt
to distinguish the current failed/passed behavior. No application behavior has
been changed to make either fixture pass.

## Exact headless check

After root dependency setup, from the repository root:

```bash
docker build --file execution/Dockerfile --tag code-aid-runner:0.1.0 .
PYTHONPATH=backend .venv/bin/python test-fixtures/check_zip_cases.py
```

Expected output:

```text
broken-python-project.zip: failed (expected), pytest exit 1
corrected-python-project.zip: passed (expected), pytest exit 0
Both ZIP cases verified in Docker; no uploaded code executed on the host.
```

The checker exits nonzero for unavailable execution, skipped tests, wrong
outcomes, or import/collection failures. It ingests the actual committed ZIPs
into temporary directories and invokes the normal generated-test pipeline.
It does not require the API/frontend or retain investigation records. To use
a nonstandard Docker CLI path, pass `--docker /path/to/docker`.

## Corrected archive contents and rebuild

The corrected ZIP contains exactly four files under `corrected-python-project/`:
`calculator.py`, `metadata.json`, `traceback.txt`, and `README.md`.

```bash
.venv/bin/python test-fixtures/build_corrected_zip.py
.venv/bin/python test-fixtures/build_corrected_zip.py --check
```

The standard-library builder uses sorted entries, fixed timestamps and file
modes, no private inputs, and no platform-specific compression metadata.
The original broken archive and source remain unchanged. See the individual
[broken](broken-python-project/README.md) and
[corrected](corrected-python-project/README.md) READMEs for their source behavior.
