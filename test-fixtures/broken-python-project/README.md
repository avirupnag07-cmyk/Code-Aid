# Broken Python smoke-test project

This small, credential-free fixture is intentionally broken so it can be
uploaded to Code-Aid through the ZIP-only web workflow.

Expected signal:

- `calculator.py` combines a numeric amount with a text tax label.
- `traceback.txt` records the resulting `TypeError`.
- `metadata.json` gives Code-Aid a safe function call and expected result for
  generated-test validation.

This fixture contains no credentials, personal paths, network calls, or
machine-specific information.
