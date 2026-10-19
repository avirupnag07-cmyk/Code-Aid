"""Tooling checks stay offline; container execution is explicitly opt-in."""

import importlib.util
import os
from pathlib import Path
import subprocess

import pytest

from app.engine import runner


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("local_doctor", ROOT / "scripts/doctor.py")
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


def test_doctor_accepts_local_runtime_patch_difference(capsys):
    assert doctor.check_version("Python", "3.9.6", "3.9.21", (3, 9, 0))
    assert "WARN Python" in capsys.readouterr().out
    assert not doctor.check_version("Python", "3.8.20", "3.9.21", (3, 9, 0))


def test_doctor_reports_missing_dependencies_without_leaking_tool_errors(monkeypatch, capsys):
    def failed_tool(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, "private stdout", "secret=private stderr")

    monkeypatch.setattr(doctor.subprocess, "run", failed_tool)
    assert doctor.main([]) == 1
    output = capsys.readouterr().out
    assert "FAIL backend dependencies" in output
    assert "FAIL Docker CLI/daemon" in output
    assert "private" not in output
    assert "secret" not in output


def test_doctor_handles_missing_cli_and_hung_daemon(monkeypatch):
    def missing_tool(*args, **kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(doctor.subprocess, "run", missing_tool)
    assert doctor.probe(["missing"]) is None

    def hung_tool(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 30)

    monkeypatch.setattr(doctor.subprocess, "run", hung_tool)
    assert doctor.probe(["docker", "version"]) is None


@pytest.mark.skipif(not os.environ.get("CODE_AID_TEST_DOCKER"), reason="opt-in Docker integration")
def test_runner_image_accepts_backend_command_and_preserves_isolation(tmp_path):
    project = tmp_path / "project"
    project.mkdir(mode=0o755)
    # The backend mounts generated tests inside a read-only project mount.
    # Docker needs this nested mountpoint to exist in the source directory.
    (project / "generated_tests").mkdir(mode=0o755)
    result = runner.run_generated_tests(
        project,
        [{"path": "generated_tests/test_smoke.py", "content": """
import os
from pathlib import Path
import socket
import pytest

def test_isolated_runtime():
    assert os.getuid() == 65532
    assert not Path('/var/run/docker.sock').exists()
    with pytest.raises(OSError):
        Path('/workspace/host-write').write_text('not allowed')
    with pytest.raises(OSError):
        socket.create_connection(('192.0.2.1', 80), timeout=0.1)
"""}],
        docker_binary=os.environ["CODE_AID_TEST_DOCKER"],
    )
    assert result["status"] == "passed", result
