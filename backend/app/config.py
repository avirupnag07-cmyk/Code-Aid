"""Environment-backed configuration for the Code-Aid service.

The defaults are relative to the checked-out project.  This keeps the service
portable between a local checkout and the container image without embedding a
machine-specific path.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Dict, Mapping, Optional, Tuple


_LOCAL_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def _read_dotenv(path: Path) -> Dict[str, str]:
    """Read single-line dotenv assignments as data, without modifying os.environ.

    Quotes are removed, but escapes, shell syntax and variable references stay
    literal. Malformed assignments are ignored; no shell is involved.
    """
    try:
        contents = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}
    values = {}
    for line in contents.splitlines():
        match = re.fullmatch(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)", line)
        if match is None:
            continue
        name, value = match.groups()
        value = value.strip()
        if value.startswith(("'", '"')):
            quoted = re.fullmatch(r"(['\"])(.*?)\1\s*(?:#.*)?", value)
            if quoted is None:
                continue
            value = quoted.group(2)
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
            if value.startswith("#"):
                value = ""
        values[name] = value
    return values


def _int_env(env: Mapping[str, str], name: str, default: int) -> int:
    value = env.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _path_env(env: Mapping[str, str], name: str, default: Path, base_dir: Path) -> Path:
    value = env.get(name)
    if not value:
        return default
    path = Path(value).expanduser()
    return path if path.is_absolute() else base_dir / path


@dataclass(frozen=True)
class Settings:
    """Runtime settings used by API routes and engine modules."""

    project_root: Path
    database_path: Path
    storage_dir: Path
    samples_dir: Path
    max_upload_bytes: int = 10 * 1024 * 1024
    max_archive_members: int = 200
    max_archive_uncompressed_bytes: int = 25 * 1024 * 1024
    max_archive_member_bytes: int = 5 * 1024 * 1024
    max_traceback_chars: int = 100_000
    max_source_file_bytes: int = 512 * 1024
    run_timeout_seconds: int = 20
    docker_image: str = "code-aid-runner:0.1.0"
    allowed_origins: Tuple[str, ...] = _LOCAL_ORIGINS

    @classmethod
    def from_env(cls, project_root: Optional[Path] = None) -> "Settings":
        # config.py lives in <repository>/backend/app, three directory levels up.
        root = (project_root or Path(__file__).resolve().parent.parent.parent).resolve()
        env = _read_dotenv(root / ".env")
        env.update(os.environ)
        backend_dir = root / "backend"
        database = _path_env(env, "CODE_AID_DATABASE", backend_dir / "data" / "code_aid.sqlite3", root)
        storage = _path_env(env, "CODE_AID_STORAGE", backend_dir / "data" / "investigations", root)
        samples = _path_env(env, "CODE_AID_SAMPLES", root / "samples", root)
        origins_value = env.get("CODE_AID_ALLOWED_ORIGINS", "")
        origins = tuple(item.strip() for item in origins_value.split(",") if item.strip()) or _LOCAL_ORIGINS
        return cls(
            project_root=root,
            database_path=database,
            storage_dir=storage,
            samples_dir=samples,
            max_upload_bytes=_int_env(env, "CODE_AID_MAX_UPLOAD_BYTES", 10 * 1024 * 1024),
            max_archive_members=_int_env(env, "CODE_AID_MAX_ARCHIVE_MEMBERS", 200),
            max_archive_uncompressed_bytes=_int_env(env, "CODE_AID_MAX_ARCHIVE_BYTES", 25 * 1024 * 1024),
            max_archive_member_bytes=_int_env(env, "CODE_AID_MAX_ARCHIVE_MEMBER_BYTES", 5 * 1024 * 1024),
            max_traceback_chars=_int_env(env, "CODE_AID_MAX_TRACEBACK_CHARS", 100_000),
            max_source_file_bytes=_int_env(env, "CODE_AID_MAX_SOURCE_FILE_BYTES", 512 * 1024),
            run_timeout_seconds=_int_env(env, "CODE_AID_RUN_TIMEOUT_SECONDS", 20),
            docker_image=env.get("CODE_AID_DOCKER_IMAGE", "code-aid-runner:0.1.0"),
            allowed_origins=origins,
        )
