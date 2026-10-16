"""Safe, public HTTPS Git repository ingestion.

The importer deliberately uses Git as a list of arguments.  It never invokes a
shell, initializes submodules, writes credentials, or exposes Git's stderr to
API callers.  Branches and tags are resolved to the checked-out commit and the
resolved SHA is retained as the durable pin for an investigation.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import ipaddress
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Sequence
from urllib.parse import urlparse

from .ingestion import (
    IngestedProject,
    IngestionError,
    IngestionLimits,
    _copy_tree_safely,
    _metadata_and_traceback,
)


class GitImportError(IngestionError):
    """Raised for invalid, unavailable, or unsafe Git repository input."""


@dataclass(frozen=True)
class RepositoryLocation:
    provider: str
    url: str
    owner: str
    name: str


@dataclass(frozen=True)
class GitCommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


CommandRunner = Callable[[Sequence[str], Path, float], GitCommandResult]

_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@+-]{0,255}$")
_ALLOWED_PUBLIC_HOSTS = {"github.com", "gitlab.com", "bitbucket.org"}


def _public_hostname(hostname: str) -> bool:
    lowered = hostname.rstrip(".").lower()
    if lowered.endswith(".local"):
        return False
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def validate_repository_url(url: str) -> RepositoryLocation:
    """Validate and normalize a public HTTPS Git URL without resolving DNS."""

    if not isinstance(url, str) or len(url) > 2048:
        raise GitImportError("repository URL is invalid")
    candidate = url.strip()
    parsed = urlparse(candidate)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise GitImportError("repository URL must use HTTPS")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise GitImportError("repository URL must not contain credentials or query parameters")
    try:
        port = parsed.port
    except ValueError as exc:
        raise GitImportError("repository URL is invalid") from exc
    if port not in (None, 443):
        raise GitImportError("repository URL must use HTTPS port 443")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname not in _ALLOWED_PUBLIC_HOSTS or not _public_hostname(hostname):
        raise GitImportError("repository host is not an allowed public Git provider")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or any(part in {".", ".."} or "\\" in part for part in parts):
        raise GitImportError("repository URL must include an owner and repository name")
    name = parts[-1]
    if name.lower().endswith(".git"):
        name = name[:-4]
    if not name or any(character in name for character in "\x00\r\n"):
        raise GitImportError("repository name is invalid")
    owner = "/".join(parts[:-1])
    provider = {
        "github.com": "github",
        "gitlab.com": "gitlab",
        "bitbucket.org": "bitbucket",
    }.get(hostname, hostname)
    normalized = "https://{}{}".format(hostname, parsed.path.rstrip("/"))
    return RepositoryLocation(provider=provider, url=normalized, owner=owner, name=name)


def validate_revision(ref: str) -> str:
    if not isinstance(ref, str):
        raise GitImportError("repository ref is required")
    value = ref.strip()
    if not value or len(value) > 256 or value.startswith("-") or ".." in value:
        raise GitImportError("repository ref is invalid")
    if not _REF_RE.fullmatch(value):
        raise GitImportError("repository ref is invalid")
    if value.endswith("/") or value.endswith(".") or "@{" in value:
        raise GitImportError("repository ref is invalid")
    return value


def validate_subdirectory(subdirectory: Optional[str]) -> Optional[str]:
    if subdirectory is None:
        return None
    if not isinstance(subdirectory, str) or not subdirectory.strip():
        raise GitImportError("repository subdirectory is invalid")
    value = subdirectory.strip().replace("\\", "/")
    path = PurePosixPath(value)
    if value.startswith("/") or any(part in {"", ".", ".."} for part in path.parts):
        raise GitImportError("repository subdirectory must stay inside the repository")
    return path.as_posix()


def _default_command_runner(args: Sequence[str], cwd: Path, timeout: float, auth_token: Optional[str] = None) -> GitCommandResult:
    environment = dict(os.environ)
    for key in (
        "GIT_ASKPASS",
        "SSH_ASKPASS",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_KEY_0",
        "GIT_CONFIG_VALUE_0",
        "GIT_CREDENTIAL_HELPER",
    ):
        environment.pop(key, None)
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
    )
    if auth_token:
        # Keep the token out of argv, URLs, Git config files, and logs. Git
        # reads the header only in this child process and the environment is
        # discarded after the command exits.
        import base64

        encoded = base64.b64encode((auth_token + ":x-oauth-basic").encode("utf-8")).decode("ascii")
        environment.update(
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
                "GIT_CONFIG_VALUE_0": "AUTHORIZATION: basic {}".format(encoded),
            }
        )
    try:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd),
            env=environment,
            check=False,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitImportError("repository import timed out") from exc
    except OSError as exc:
        if getattr(exc, "errno", None) == 2:
            raise GitImportError("Git is not available on the server") from exc
        raise GitImportError("repository import could not start") from exc
    return GitCommandResult(completed.returncode, completed.stdout[-4096:], completed.stderr[-4096:])


def build_git_commands(repository_url: str, ref: str, checkout_path: Path) -> List[List[str]]:
    """Return the exact safe Git argv sequence used by ``import_repository``."""

    return [
        ["git", "init", "--quiet", str(checkout_path)],
        ["git", "-C", str(checkout_path), "remote", "add", "origin", repository_url],
        [
            "git",
            "-C",
            str(checkout_path),
            "fetch",
            "--depth",
            "1",
            "--no-tags",
            "--no-recurse-submodules",
            "origin",
            ref,
        ],
        ["git", "-C", str(checkout_path), "checkout", "--detach", "--force", "FETCH_HEAD"],
        ["git", "-C", str(checkout_path), "rev-parse", "HEAD"],
    ]


def _run_checked(runner: CommandRunner, args: Sequence[str], cwd: Path, timeout: float, message: str) -> GitCommandResult:
    result = runner(args, cwd, timeout)
    if result.returncode != 0:
        raise GitImportError(message)
    return result


def import_repository(
    repository_url: str,
    ref: str,
    destination: Path,
    *,
    subdirectory: Optional[str] = None,
    limits: Optional[IngestionLimits] = None,
    timeout_seconds: int = 60,
    command_runner: Optional[CommandRunner] = None,
    auth_token: Optional[str] = None,
) -> IngestedProject:
    """Fetch and copy a public repository at a resolved, exact revision."""

    location = validate_repository_url(repository_url)
    selected_ref = validate_revision(ref)
    selected_subdirectory = validate_subdirectory(subdirectory)
    if timeout_seconds < 1:
        raise GitImportError("repository timeout is invalid")
    destination = destination.resolve()
    if destination.exists():
        raise GitImportError("destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if auth_token and location.provider != "github":
        raise GitImportError("authenticated imports are only supported for GitHub")
    runner = command_runner or (lambda args, cwd, timeout: _default_command_runner(args, cwd, timeout, auth_token=auth_token))
    checkout_path = Path(tempfile.mkdtemp(prefix=".git-import-", dir=str(destination.parent)))
    deadline = time.monotonic() + float(timeout_seconds)
    try:
        commands = build_git_commands(location.url, selected_ref, checkout_path)
        for index, command in enumerate(commands[:-1]):
            remaining = max(0.1, deadline - time.monotonic())
            _run_checked(
                runner,
                command,
                destination.parent,
                remaining,
                "repository revision could not be fetched" if index == 2 else "repository import failed",
            )
        revision = _run_checked(
            runner,
            commands[-1],
            destination.parent,
            max(0.1, deadline - time.monotonic()),
            "repository revision could not be resolved",
        ).stdout.strip()
        if not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
            raise GitImportError("repository revision could not be resolved")
        source_root = checkout_path
        if selected_subdirectory:
            source_root = (checkout_path / selected_subdirectory).resolve()
            try:
                source_root.relative_to(checkout_path.resolve())
            except ValueError as exc:
                raise GitImportError("repository subdirectory is unsafe") from exc
            if source_root.is_symlink() or not source_root.is_dir():
                raise GitImportError("repository subdirectory was not found")
        files = _copy_tree_safely(source_root, destination, limits or IngestionLimits())
        metadata, traceback = _metadata_and_traceback(destination)
        imported_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        repository = {
            "provider": location.provider,
            "url": location.url,
            "owner": location.owner,
            "name": location.name,
            "ref": selected_ref,
            "sha": revision.lower(),
            "subdirectory": selected_subdirectory,
            "imported_at": imported_at,
        }
        return IngestedProject(
            root=destination,
            source_type="git",
            traceback=traceback,
            metadata=metadata,
            files=files,
            repository=repository,
        )
    except Exception:
        shutil.rmtree(str(destination), ignore_errors=True)
        raise
    finally:
        shutil.rmtree(str(checkout_path), ignore_errors=True)
