"""Verify public failed/passed ZIP cases through the real isolated runner."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from app.engine.ingestion import ingest_zip
from app.engine.runner import run_generated_tests
from app.engine.test_generation import generate_tests
from app.engine.traceback_parser import parse_traceback


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", default="docker", help="Docker CLI executable")
    args = parser.parse_args()
    fixtures = Path(__file__).resolve().parent
    cases = (("broken-python-project.zip", "failed", 1),
             ("corrected-python-project.zip", "passed", 0))
    for name, expected_status, expected_exit in cases:
        with TemporaryDirectory(prefix="code-aid-fixture-") as temporary:
            project = ingest_zip((fixtures / name).read_bytes(),
                                 Path(temporary) / "project", original_filename=name)
            tests = generate_tests(parse_traceback(project.traceback), project.metadata)
            if len(tests) != 1 or tests[0]["test_mode"] != "expected-output":
                parser.exit(1, name + ": expected one expected-output test\n")
            if tests[0]["validation_status"] != "valid" or "pytest.skip" in tests[0]["content"]:
                parser.exit(1, name + ": generated test is invalid or skipped\n")
            result = run_generated_tests(project.root, tests, timeout_seconds=30,
                                         docker_binary=args.docker)
            output = result["stdout"] + result["stderr"]
            valid = result["status"] == expected_status and result["exit_code"] == expected_exit
            valid = valid and "ModuleNotFoundError" not in output and "skipped" not in output.lower()
            if expected_status == "failed":
                valid = valid and "TypeError: unsupported operand type(s) for +" in output
                valid = valid and "1 failed" in output
            else:
                valid = valid and "1 passed" in output
            if not valid:
                print(output)
                parser.exit(1, "{}: unexpected {} result; {}\n".format(
                    name, result["status"], result["reason"]))
            print("{}: {} (expected), pytest exit {}".format(name, expected_status, expected_exit))
    print("Both ZIP cases verified in Docker; no uploaded code executed on the host.")


if __name__ == "__main__":
    main()
