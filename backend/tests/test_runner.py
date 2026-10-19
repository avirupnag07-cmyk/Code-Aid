from pathlib import Path
import subprocess

from app.engine import runner


def test_generated_mount_is_outside_read_only_project(monkeypatch, tmp_path):
    monkeypatch.setattr(runner.shutil, "which", lambda _binary: "/usr/bin/docker")
    commands = []

    def completed(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "1 passed", "")

    monkeypatch.setattr(runner.subprocess, "run", completed)
    result = runner.run_generated_tests(
        tmp_path,
        [{"path": "generated_tests/test_case.py", "content": "def test_x(): pass"}],
    )
    assert result["status"] == "passed"
    command = commands[0]
    assert command[-1] == "/generated-tests"
    assert any(value.endswith(":/generated-tests:ro") for value in command)
    assert not any(":/workspace/generated_tests" in value for value in command)
    assert list(tmp_path.iterdir()) == []


def test_runner_fails_safe_when_docker_is_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(runner.shutil, "which", lambda _binary: None)
    result = runner.run_generated_tests(
        tmp_path,
        [{"path": "generated_tests/test_case.py", "content": "import pytest\ndef test_x(): pass"}],
    )
    assert result["status"] == "unavailable"
    assert "not executed" in result["reason"]


def test_runner_reports_timeout(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(runner.shutil, "which", lambda _binary: "/usr/bin/docker")

    def timeout(*_args, **_kwargs):
        raise runner.subprocess.TimeoutExpired(cmd="docker", timeout=1, output=b"partial", stderr=b"slow")

    monkeypatch.setattr(runner.subprocess, "run", timeout)
    tmp_path.joinpath("module.py").write_text("value = 1")
    result = runner.run_generated_tests(
        tmp_path,
        [{"path": "generated_tests/test_case.py", "content": "import pytest\ndef test_x(): pass"}],
    )
    assert result["status"] == "timeout"
    assert "timeout" in result["reason"].lower()


def test_runner_rejects_generated_path_outside_execution_directory(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(runner.shutil, "which", lambda _binary: "/usr/bin/docker")
    result = runner.run_generated_tests(
        tmp_path,
        [{"path": "../escape.py", "content": "pass"}],
    )
    assert result["status"] == "unavailable"
    assert "outside generated_tests" in result["reason"]
