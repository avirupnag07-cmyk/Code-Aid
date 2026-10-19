# Corrected Python regression fixture

Upload `test-fixtures/corrected-python-project.zip` through Code-Aid's ZIP
workflow. This credential-free fixture implements:

```python
def total_with_tax(amount, tax_rate):
    return amount * (1 + float(tax_rate) / 100)
```

The safe `metadata.json` test specification matches the broken fixture:
module `calculator`, function `total_with_tax`, arguments `[100.0, "8"]`,
expected result `108.0`. Code-Aid should generate an **expected-output** test
that passes, with no skips.

## Historical traceback

`traceback.txt` retains the original bug report for regression testing. It
describes the old `return amount + "$" + tax_rate` implementation, **not a
current error in the corrected code**. The metadata's `exception_type` is the
historically reported exception; `traceback_status` explicitly records this.

## Rebuild and check the ZIP

From the repository root, using the existing project Python environment:

```sh
.venv/bin/python test-fixtures/build_corrected_zip.py
.venv/bin/python test-fixtures/build_corrected_zip.py --check
```

The builder uses only Python's standard library and reads fixture files as
data; it never imports or executes `calculator.py`. It prints the archive's
SHA-256. The ZIP contains exactly these sorted, UTF-8-readable files:

```text
corrected-python-project/README.md
corrected-python-project/calculator.py
corrected-python-project/metadata.json
corrected-python-project/traceback.txt
```

All entries use the fixed timestamp `1980-01-01 00:00:00`, regular-file mode
`0644`, and stored (uncompressed) bytes. There are no directory entries,
comments, extra fields, host paths, or private inputs. Stored entries avoid
compression-library differences when rebuilding on Linux or macOS.

## Validate ingestion and real isolated execution

Use the existing project setup and installed Docker runner image
`code-aid-runner:0.1.0` (built with `make runner-build`). From the repository
root, ensure the Docker CLI is on `PATH`, then run:

```sh
PYTHONPATH=backend .venv/bin/python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from app.engine.ingestion import ingest_zip
from app.engine.test_generation import generate_tests
from app.engine.traceback_parser import parse_traceback
from app.engine.runner import run_generated_tests

archive = Path("test-fixtures/corrected-python-project.zip")
with TemporaryDirectory(prefix="code-aid-corrected-") as temporary:
    project = ingest_zip(archive.read_bytes(), Path(temporary) / "project",
                         original_filename=archive.name)
    assert sorted(project.files) == [
        "corrected-python-project/" + name
        for name in ("README.md", "calculator.py", "metadata.json", "traceback.txt")
    ]
    tests = generate_tests(parse_traceback(project.traceback), project.metadata)
    assert len(tests) == 1
    assert tests[0]["validation_status"] == "valid"
    assert tests[0]["test_mode"] == "expected-output"
    assert "pytest.skip" not in tests[0]["content"]
    result = run_generated_tests(project.root, tests, timeout_seconds=30)
    print(result["stdout"], result["stderr"])
    assert result["status"] == "passed", result
    assert result["exit_code"] == 0, result
    assert "1 passed" in result["stdout"], result
    assert "skipped" not in result["stdout"].lower(), result
PY
make test
```

The host performs ingestion and test generation only. Fixture code and its
generated assertion execute inside the application's network-disabled,
read-only Docker sandbox. An unavailable Docker runner is a failed validation,
not a skip or a host-execution fallback.
