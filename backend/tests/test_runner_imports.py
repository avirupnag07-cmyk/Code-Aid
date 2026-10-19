"""Import-layout regressions at the Docker boundary, without host imports."""

import io
import os
from pathlib import Path
import subprocess
import zipfile

import pytest

from app.engine import runner
from app.engine.ingestion import ingest_zip
from app.engine.test_generation import generate_tests
from app.engine.traceback_parser import parse_traceback


FIXTURE = Path(__file__).resolve().parents[2] / "test-fixtures" / "broken-python-project"
REPORTED_WRAPPER = "project/test-fixtures/broken-python-project"
PATCHED_CALCULATOR = (
    "def total_with_tax(amount, tax_rate):\n"
    "    return amount * (1 + float(tax_rate) / 100)\n"
)


def _write_files(root, files):
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _snapshot(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _pythonpath(command):
    values = [
        command[index + 1].split("=", 1)[1]
        for index, value in enumerate(command[:-1])
        if value == "-e" and command[index + 1].startswith("PYTHONPATH=")
    ]
    assert len(values) == 1, command
    return values[0].split(":")


def _mount(command, destination):
    mounts = [
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "-v" and command[index + 1].endswith(":" + destination + ":ro")
    ]
    assert len(mounts) == 1, command
    return Path(mounts[0].rsplit(":", 2)[0])


def _assert_sandbox(command):
    assert command[1:3] == ["run", "--rm"]
    assert "--pull=never" in command
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert command[command.index("--security-opt") + 1] == "no-new-privileges:true"
    assert command[command.index("--user") + 1] == "65532:65532"
    assert command[command.index("--cpus") + 1] == "1"
    assert command[command.index("--memory") + 1] == "256m"
    assert command[command.index("--pids-limit") + 1] == "128"
    assert command[command.index("--tmpfs") + 1] == "/tmp:rw,noexec,nosuid,nodev,size=64m"
    assert "PYTHONDONTWRITEBYTECODE=1" in command
    assert command[command.index("-w") + 1] == "/workspace"
    assert command[-1] == "/generated-tests"
    assert len([value for value in command if value == "-v"]) == 2
    assert _mount(command, "/workspace") != _mount(command, "/generated-tests")


@pytest.fixture
def captured_docker(monkeypatch):
    """Inspect disposable mounts while they still exist; never execute code."""
    calls = []
    monkeypatch.setattr(runner.shutil, "which", lambda _binary: "/usr/bin/docker")

    def completed(command, **kwargs):
        _assert_sandbox(command)
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["check"] is False
        assert kwargs["timeout"] == 20
        calls.append({
            "command": list(command),
            "root": _mount(command, "/workspace"),
            "project": _snapshot(_mount(command, "/workspace")),
            "generated": _snapshot(_mount(command, "/generated-tests")),
        })
        return subprocess.CompletedProcess(command, 0, "1 passed", "")

    monkeypatch.setattr(runner.subprocess, "run", completed)
    return calls


def _generated_test(module="calculator"):
    return [{
        "path": "generated_tests/test_calculator.py",
        "content": (
            "import pytest\n"
            "from {} import total_with_tax\n\n"
            "def test_total_with_tax():\n"
            "    assert total_with_tax(100.0, '8') == 108.0\n"
        ).format(module),
    }]


@pytest.mark.parametrize(
    "files, module, expected_roots",
    [
        pytest.param(
            {"calculator.py": PATCHED_CALCULATOR},
            "calculator", ["/workspace"], id="flat-calculator",
        ),
        pytest.param(
            {REPORTED_WRAPPER + "/calculator.py": PATCHED_CALCULATOR},
            "calculator",
            ["/workspace", "/workspace/project", "/workspace/project/test-fixtures",
             "/workspace/" + REPORTED_WRAPPER],
            id="reported-nested-zip-path",
        ),
        pytest.param(
            {"src/calculator.py": PATCHED_CALCULATOR},
            "calculator", ["/workspace", "/workspace/src"], id="root-src",
        ),
        pytest.param(
            {"wrapper/src/calculator.py": PATCHED_CALCULATOR},
            "calculator", ["/workspace", "/workspace/wrapper", "/workspace/wrapper/src"],
            id="wrapper-src",
        ),
        pytest.param(
            {"taxes/__init__.py": "", "taxes/calculator.py": PATCHED_CALCULATOR},
            "taxes.calculator", ["/workspace"], id="dotted-package-not-flattened",
        ),
        pytest.param(
            {"wrapper/taxes/__init__.py": "", "wrapper/taxes/calculator.py": PATCHED_CALCULATOR},
            "taxes.calculator", ["/workspace", "/workspace/wrapper"],
            id="wrapped-package-not-flattened",
        ),
        pytest.param(
            {"src/taxes/__init__.py": "", "src/taxes/calculator.py": PATCHED_CALCULATOR},
            "taxes.calculator", ["/workspace", "/workspace/src"],
            id="src-package-not-flattened",
        ),
        pytest.param(
            {"first/calculator.py": PATCHED_CALCULATOR, "second/calculator.py": "raise RuntimeError()"},
            "first.calculator", ["/workspace"], id="sibling-projects-not-promoted",
        ),
        pytest.param(
            {"wrapper/first/calculator.py": PATCHED_CALCULATOR,
             "wrapper/second/calculator.py": "raise RuntimeError()"},
            "first.calculator", ["/workspace", "/workspace/wrapper"],
            id="wrapped-sibling-projects-not-promoted",
        ),
        pytest.param(
            {".DS_Store": "finder metadata", "__MACOSX/._wrapper": "resource fork",
             "._wrapper": "resource fork", "wrapper/.DS_Store": "finder metadata",
             "wrapper/__MACOSX/._calculator.py": "resource fork",
             "wrapper/calculator.py": PATCHED_CALCULATOR},
            "calculator", ["/workspace", "/workspace/wrapper"], id="macos-wrapper-artifacts",
        ),
    ],
)
def test_import_roots_in_docker_command(tmp_path, captured_docker, files, module, expected_roots):
    _write_files(tmp_path, files)
    before = _snapshot(tmp_path)
    tests = _generated_test(module)

    result = runner.run_generated_tests(tmp_path, tests)

    assert result["status"] == "passed", result
    assert len(captured_docker) == 1
    captured = captured_docker[0]
    assert _pythonpath(captured["command"]) == expected_roots
    assert result["command"] == captured["command"]
    assert captured["root"] == tmp_path.resolve()
    assert captured["project"] == before
    assert captured["generated"] == {tests[0]["path"]: tests[0]["content"].encode("utf-8")}
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("source_dir", [REPORTED_WRAPPER, "wrapper/src"])
def test_file_overrides_discover_staged_roots_and_preserve_original_bytes(
    tmp_path, captured_docker, source_dir,
):
    # Adding src only in the override catches discovery against the original tree.
    wrapper = source_dir.rsplit("/src", 1)[0] if source_dir.endswith("/src") else source_dir
    _write_files(tmp_path, {
        wrapper + "/metadata.json": (FIXTURE / "metadata.json").read_text(encoding="utf-8"),
        wrapper + "/calculator.py": (FIXTURE / "calculator.py").read_text(encoding="utf-8"),
        wrapper + "/generated_tests/uploaded.txt": "keep uploaded files\n",
    })
    before = _snapshot(tmp_path)
    relative = source_dir + "/calculator.py"

    result = runner.run_generated_tests(
        tmp_path, _generated_test(), file_overrides={relative: PATCHED_CALCULATOR},
    )

    assert result["status"] == "passed", result
    assert len(captured_docker) == 1
    captured = captured_docker[0]
    expected_roots = ["/workspace"]
    for index in range(1, len(Path(wrapper).parts) + 1):
        expected_roots.append("/workspace/" + "/".join(Path(wrapper).parts[:index]))
    if source_dir.endswith("/src"):
        expected_roots.append("/workspace/" + source_dir)
    assert _pythonpath(captured["command"]) == expected_roots
    assert captured["root"] != tmp_path.resolve()
    assert captured["project"] == {**before, relative: PATCHED_CALCULATOR.encode("utf-8")}
    assert _snapshot(tmp_path) == before
    assert not captured["root"].exists(), "Disposable patched source must be cleaned up"


def _ingest_calculator_zip(tmp_path, source_dir):
    """Re-create the reported wrapper hierarchy from public repository fixtures."""
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        for source in sorted(FIXTURE.iterdir()):
            archive.writestr(source_dir + "/" + source.name, source.read_bytes())
        archive.writestr(".DS_Store", b"finder metadata")
        archive.writestr("__MACOSX/._project", b"resource fork")
    project = ingest_zip(payload.getvalue(), tmp_path / "project", original_filename="calculator.zip")
    tests = generate_tests(parse_traceback(project.traceback), project.metadata)
    assert project.metadata["module"] == "calculator"
    assert project.metadata["test_spec"]["function"] == "total_with_tax"
    assert tests[0]["validation_status"] == "valid"
    assert tests[0]["test_mode"] == "expected-output"
    assert "from calculator import total_with_tax" in tests[0]["content"]
    return project, tests


@pytest.mark.skipif(not os.environ.get("CODE_AID_TEST_DOCKER"), reason="opt-in Docker integration")
@pytest.mark.parametrize("source_dir", [REPORTED_WRAPPER, "src", "wrapper/src"])
def test_real_docker_imports_reach_calculator_typeerror_then_patched_override_passes(tmp_path, source_dir):
    project, tests = _ingest_calculator_zip(tmp_path, source_dir)
    before = _snapshot(project.root)
    options = {"docker_binary": os.environ["CODE_AID_TEST_DOCKER"], "timeout_seconds": 30}

    baseline = runner.run_generated_tests(project.root, tests, **options)

    output = baseline["stdout"] + baseline["stderr"]
    assert baseline["status"] == "failed", baseline
    assert baseline["exit_code"] == 1, output
    assert "TypeError: unsupported operand type(s) for +" in output, output
    assert 'return amount + "$" + tax_rate' in output, output
    assert "ModuleNotFoundError" not in output, output
    assert "ImportError" not in output, output
    _assert_sandbox(baseline["command"])

    patched = runner.run_generated_tests(
        project.root, tests,
        file_overrides={source_dir + "/calculator.py": PATCHED_CALCULATOR}, **options,
    )

    assert patched["status"] == "passed", patched
    assert patched["exit_code"] == 0, patched
    assert "1 passed" in patched["stdout"], patched
    _assert_sandbox(patched["command"])
    assert _pythonpath(patched["command"]) == _pythonpath(baseline["command"])
    assert _snapshot(project.root) == before
