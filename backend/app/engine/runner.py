"""Docker-only execution of generated tests.

The host process never imports or runs project code.  When Docker is absent,
the result is an explicit ``unavailable`` record rather than a local fallback.
"""

from datetime import datetime, timezone
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _text(value: Any, limit: int = 100_000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value)[:limit]


def _safe_generated_path(path: str) -> Path:
    normalized = path.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if "\x00" in normalized or normalized.startswith("/") or ".." in pure.parts or "." in pure.parts or not normalized.startswith("generated_tests/"):
        raise ValueError("generated test path is outside generated_tests/")
    return Path(*pure.parts)


def _safe_project_path(path: str) -> Path:
    normalized = path.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if not normalized or "\x00" in normalized or normalized.startswith("/") or ".." in pure.parts or ":" in pure.parts[0]:
        raise ValueError("project override path is not a safe relative path")
    return Path(*pure.parts)


def _unavailable(reason: str, command: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "status": "unavailable",
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "duration_ms": 0,
        "reason": reason,
        "command": command or [],
        "started_at": _now(),
        "finished_at": _now(),
    }


def _safe_project_root(project_root: Path) -> Path:
    root = project_root.resolve()
    if not root.is_dir() or project_root.is_symlink():
        raise ValueError("project root is not a safe directory")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("project contains a symlink")
        if not path.is_dir() and not path.is_file():
            raise ValueError("project contains a non-regular filesystem entry")
    return root


def _staged_project(root: Path, overrides: Mapping[str, str]) -> Path:
    """Make a disposable source copy and apply text overrides as data."""

    staging = Path(tempfile.mkdtemp(prefix="code-aid-patched-")) / "project"
    try:
        shutil.copytree(str(root), str(staging), symlinks=False)
        os.chmod(str(staging.parent), 0o755)
        os.chmod(str(staging), 0o755)
        for raw_path, content in overrides.items():
            relative = _safe_project_path(str(raw_path))
            if len(str(content).encode("utf-8")) > 512 * 1024:
                raise ValueError("project override exceeds the execution size limit")
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(content), encoding="utf-8")
            os.chmod(str(target), 0o644)
        return staging
    except Exception:
        shutil.rmtree(str(staging.parent), ignore_errors=True)
        raise


def run_generated_tests(
    project_root: Path,
    generated_tests: Sequence[Mapping[str, Any]],
    *,
    timeout_seconds: int = 20,
    docker_image: str = "code-aid-runner:0.1.0",
    docker_binary: str = "docker",
    file_overrides: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Run generated tests only inside a network-disabled Docker container."""

    if not generated_tests:
        return _unavailable("No generated tests are available to run.")
    if shutil.which(docker_binary) is None:
        return _unavailable("Docker is not installed or is not available on PATH; project code was not executed.")
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be positive")
    root = _safe_project_root(project_root)
    started = _now()
    start_time = time.monotonic()
    staging_parent: Optional[Path] = None
    execution_root = root
    if file_overrides:
        try:
            execution_root = _staged_project(root, file_overrides)
            staging_parent = execution_root.parent
        except (OSError, ValueError, shutil.Error) as exc:
            return _unavailable("Proposed source could not be staged safely: {}".format(exc))
    try:
        with tempfile.TemporaryDirectory(prefix="code-aid-generated-") as generated_dir_name:
            generated_dir = Path(generated_dir_name)
            os.chmod(str(generated_dir), 0o755)
            try:
                for generated in generated_tests:
                    relative = _safe_generated_path(str(generated.get("path") or ""))
                    content = str(generated.get("content") or "")
                    if len(content.encode("utf-8")) > 512 * 1024:
                        return _unavailable("Generated test exceeds the execution size limit.")
                    target = generated_dir / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.chmod(str(target.parent), 0o755)
                    target.write_text(content, encoding="utf-8")
                    os.chmod(str(target), 0o644)
            except (OSError, ValueError) as exc:
                return _unavailable("Generated test could not be prepared: {}".format(exc))

            command = [
                docker_binary,
                "run",
                "--rm",
                "--pull=never",
                "--network",
                "none",
                "--cpus",
                "1",
                "--memory",
                "256m",
                "--pids-limit",
                "128",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--user",
                "65532:65532",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=64m",
                "-e",
                "PYTHONDONTWRITEBYTECODE=1",
                "-e",
                "PYTHONPATH=/workspace",
                "-v",
                "{}:/workspace:ro".format(execution_root),
                "-v",
                "{}:/workspace/generated_tests:ro".format(generated_dir),
                "-w",
                "/workspace",
                docker_image,
                "python",
                "-m",
                "pytest",
                "-q",
                "--disable-warnings",
                "--no-header",
                "-p",
                "no:cacheprovider",
                "/workspace/generated_tests",
            ]
            try:
                completed = subprocess.run(
                    command,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
                returncode = int(completed.returncode)
                stderr = _text(completed.stderr)
                unavailable_markers = (
                    "cannot connect to the docker daemon",
                    "is the docker daemon running",
                    "no such image",
                    "pull access denied",
                    "image not found",
                )
                unavailable = any(marker in stderr.lower() for marker in unavailable_markers)
                if unavailable:
                    status = "unavailable"
                    reason = "Docker could not provide the configured isolated runtime; project code was not run."
                else:
                    status = "passed" if returncode == 0 else "failed"
                    reason = ""
                return {
                    "status": status,
                    "exit_code": returncode,
                    "stdout": _text(completed.stdout),
                    "stderr": stderr,
                    "duration_ms": int((time.monotonic() - start_time) * 1000),
                    "reason": reason,
                    "command": command,
                    "started_at": started,
                    "finished_at": _now(),
                }
            except subprocess.TimeoutExpired as exc:
                return {
                    "status": "timeout",
                    "exit_code": None,
                    "stdout": _text(getattr(exc, "stdout", "")),
                    "stderr": _text(getattr(exc, "stderr", "")),
                    "duration_ms": int((time.monotonic() - start_time) * 1000),
                    "reason": "Generated tests exceeded the Docker execution timeout.",
                    "command": command,
                    "started_at": started,
                    "finished_at": _now(),
                }
            except FileNotFoundError:
                return _unavailable("Docker became unavailable before execution; project code was not run.", command)
            except OSError as exc:
                return {
                    "status": "error",
                    "exit_code": None,
                    "stdout": "",
                    "stderr": str(exc),
                    "duration_ms": int((time.monotonic() - start_time) * 1000),
                    "reason": "Docker execution failed before pytest started.",
                    "command": command,
                    "started_at": started,
                    "finished_at": _now(),
                }
    finally:
        if staging_parent is not None:
            shutil.rmtree(str(staging_parent), ignore_errors=True)


run_tests = run_generated_tests
