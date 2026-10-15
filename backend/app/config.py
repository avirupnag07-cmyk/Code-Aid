"""Environment-backed configuration for the Code-Aid service.

The defaults are relative to the checked-out project.  This keeps the service
portable between a local checkout and the container image without embedding a
machine-specific path.
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional, Tuple


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _path_env(name: str, default: Path, base_dir: Path) -> Path:
    value = os.getenv(name)
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
    docker_image: str = "python:3.9-slim"
    allowed_origins: Tuple[str, ...] = ("*",)

    @classmethod
    def from_env(cls, project_root: Optional[Path] = None) -> "Settings":
        root = (project_root or Path(__file__).resolve().parents[2]).resolve()
        backend_dir = root / "backend"
        database = _path_env("CODE_AID_DATABASE", backend_dir / "data" / "code_aid.sqlite3", root)
        storage = _path_env("CODE_AID_STORAGE", backend_dir / "data" / "investigations", root)
        samples = _path_env("CODE_AID_SAMPLES", root / "samples", root)
        origins_value = os.getenv("CODE_AID_ALLOWED_ORIGINS", "*")
        origins = tuple(item.strip() for item in origins_value.split(",") if item.strip()) or ("*",)
        return cls(
            project_root=root,
            database_path=database,
            storage_dir=storage,
            samples_dir=samples,
            max_upload_bytes=_int_env("CODE_AID_MAX_UPLOAD_BYTES", 10 * 1024 * 1024),
            max_archive_members=_int_env("CODE_AID_MAX_ARCHIVE_MEMBERS", 200),
            max_archive_uncompressed_bytes=_int_env("CODE_AID_MAX_ARCHIVE_BYTES", 25 * 1024 * 1024),
            max_archive_member_bytes=_int_env("CODE_AID_MAX_ARCHIVE_MEMBER_BYTES", 5 * 1024 * 1024),
            max_traceback_chars=_int_env("CODE_AID_MAX_TRACEBACK_CHARS", 100_000),
            max_source_file_bytes=_int_env("CODE_AID_MAX_SOURCE_FILE_BYTES", 512 * 1024),
            run_timeout_seconds=_int_env("CODE_AID_RUN_TIMEOUT_SECONDS", 20),
            docker_image=os.getenv("CODE_AID_DOCKER_IMAGE", "python:3.9-slim"),
            allowed_origins=origins,
        )
