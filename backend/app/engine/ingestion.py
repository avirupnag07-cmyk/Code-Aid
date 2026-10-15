"""Safe project and ZIP ingestion.

Ingestion treats every uploaded archive as untrusted bytes.  It validates all
member names and sizes before writing files, refuses symlinks, and never
imports or executes anything from the project.
"""

from dataclasses import dataclass, field
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
from typing import BinaryIO, Dict, Iterable, List, Optional, Tuple, Union
import zipfile


class IngestionError(ValueError):
    """Base error returned for malformed or unsafe project input."""


class UnsafeArchiveError(IngestionError):
    """Raised when an archive member would escape the extraction directory."""


class ArchiveLimitError(IngestionError):
    """Raised when an archive exceeds configured resource limits."""


IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    "build",
    "dist",
}


@dataclass(frozen=True)
class IngestionLimits:
    max_members: int = 200
    max_uncompressed_bytes: int = 25 * 1024 * 1024
    max_member_bytes: int = 5 * 1024 * 1024
    max_source_file_bytes: int = 512 * 1024


@dataclass
class IngestedProject:
    root: Path
    source_type: str
    sample_id: Optional[str] = None
    original_filename: Optional[str] = None
    traceback: str = ""
    metadata: Dict[str, object] = field(default_factory=dict)
    files: List[str] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)


def _safe_member_path(name: str) -> Path:
    """Return a relative path or reject absolute/traversal names."""

    if not name or "\x00" in name:
        raise UnsafeArchiveError("archive member has an invalid name")
    normalized = name.replace("\\", "/")
    if normalized.startswith("/"):
        raise UnsafeArchiveError("absolute archive paths are not allowed")
    # Reject Windows drive prefixes even on Unix hosts.
    if len(normalized) >= 2 and normalized[1] == ":":
        raise UnsafeArchiveError("drive-qualified archive paths are not allowed")
    parts = PurePosixPath(normalized).parts
    if any(part in ("..", "") for part in parts):
        raise UnsafeArchiveError("archive path traversal is not allowed")
    if any(part == "." for part in parts):
        raise UnsafeArchiveError("dot archive paths are not allowed")
    return Path(*parts)


def _ensure_inside(root: Path, candidate: Path) -> None:
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise UnsafeArchiveError("archive member escapes the extraction directory") from exc


def _read_limited(path: Path, max_bytes: int) -> str:
    data = path.read_bytes()
    if len(data) > max_bytes:
        raise IngestionError("source file exceeds the configured size limit")
    return data.decode("utf-8", errors="replace")


def _metadata_and_traceback(root: Path, max_traceback_chars: int = 100_000) -> Tuple[Dict[str, object], str]:
    metadata: Dict[str, object] = {}
    metadata_candidates = sorted(
        (path for path in root.rglob("*.json") if path.is_file() and not path.is_symlink()),
        key=lambda item: (len(item.relative_to(root).parts), item.as_posix()),
    )
    for path in metadata_candidates:
        if path.name.lower() not in {"metadata.json", "code-aid.json", "sample.json"}:
            continue
        try:
            value = json.loads(_read_limited(path, 256 * 1024))
        except (OSError, ValueError):
            continue
        if isinstance(value, dict):
            metadata = value
            break

    traceback_candidates = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and path.name.lower() in {"traceback.txt", "traceback.log", "error.txt", "error.log"}
        ),
        key=lambda item: (len(item.relative_to(root).parts), item.as_posix()),
    )
    traceback = ""
    if traceback_candidates:
        traceback = _read_limited(traceback_candidates[0], max_traceback_chars)
    configured = metadata.get("traceback")
    if not traceback and isinstance(configured, str):
        traceback = configured[:max_traceback_chars]
    if not traceback and isinstance(metadata.get("traceback_file"), str):
        candidate = root / str(metadata["traceback_file"])
        try:
            _ensure_inside(root, candidate)
            if candidate.is_file() and not candidate.is_symlink():
                traceback = _read_limited(candidate, max_traceback_chars)
        except (OSError, IngestionError):
            pass
    return metadata, traceback


def _collect_files(root: Path) -> List[str]:
    files: List[str] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise UnsafeArchiveError("symlinks are not allowed in project input")
        if path.is_file():
            relative = path.relative_to(root)
            if any(part in IGNORED_DIRECTORIES for part in relative.parts):
                continue
            files.append(relative.as_posix())
    return files


def _copy_tree_safely(source: Path, destination: Path, limits: IngestionLimits) -> List[str]:
    if source.is_symlink() or not source.is_dir():
        raise IngestionError("project source is not a regular directory")
    destination.mkdir(parents=True, exist_ok=False)
    try:
        files: List[str] = []
        for source_path in sorted(source.rglob("*"), key=lambda item: item.as_posix()):
            relative = source_path.relative_to(source)
            if any(part in IGNORED_DIRECTORIES for part in relative.parts):
                continue
            target = destination / relative
            _ensure_inside(destination, target)
            if source_path.is_symlink():
                raise UnsafeArchiveError("symlinks are not allowed in project input")
            if source_path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not source_path.is_file():
                continue
            size = source_path.stat().st_size
            if size > limits.max_source_file_bytes:
                raise ArchiveLimitError("source file exceeds the configured size limit")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(source_path), str(target))
            files.append(relative.as_posix())
        return files
    except Exception:
        shutil.rmtree(str(destination), ignore_errors=True)
        raise


class SampleCatalog:
    """Read-only catalog of bundled samples."""

    def __init__(self, samples_dir: Path, limits: Optional[IngestionLimits] = None):
        self.samples_dir = samples_dir
        self.limits = limits or IngestionLimits()

    @staticmethod
    def _valid_id(sample_id: str) -> bool:
        return bool(sample_id) and all(character.isalnum() or character in "-_" for character in sample_id)

    def _path(self, sample_id: str) -> Path:
        if not self._valid_id(sample_id):
            raise IngestionError("invalid sample id")
        candidate = (self.samples_dir / sample_id).resolve()
        try:
            candidate.relative_to(self.samples_dir.resolve())
        except ValueError as exc:
            raise IngestionError("sample is outside the bundled sample directory") from exc
        if not candidate.is_dir() or candidate.is_symlink():
            raise IngestionError("unknown sample")
        return candidate

    def describe(self, sample_id: str) -> Dict[str, object]:
        path = self._path(sample_id)
        metadata, traceback = _metadata_and_traceback(path)
        files = _collect_files(path)
        return {
            "id": sample_id,
            "name": str(metadata.get("name") or sample_id.replace("-", " ").title()),
            "description": str(metadata.get("description") or "Bundled Code-Aid sample"),
            "category": str(metadata.get("category") or "sample"),
            "exception_type": str(metadata.get("exception_type") or ""),
            "traceback": traceback,
            "file_count": len(files),
            "metadata": metadata,
        }

    def list(self) -> List[Dict[str, object]]:
        if not self.samples_dir.is_dir():
            return []
        descriptions: List[Dict[str, object]] = []
        for path in sorted(self.samples_dir.iterdir(), key=lambda item: item.name):
            if path.is_dir() and not path.is_symlink() and self._valid_id(path.name):
                try:
                    descriptions.append(self.describe(path.name))
                except (OSError, IngestionError):
                    continue
        return descriptions

    def ingest(self, sample_id: str, destination: Path) -> IngestedProject:
        source = self._path(sample_id)
        files = _copy_tree_safely(source, destination, self.limits)
        metadata, traceback = _metadata_and_traceback(destination)
        return IngestedProject(
            root=destination,
            source_type="sample",
            sample_id=sample_id,
            traceback=traceback,
            metadata=metadata,
            files=files,
        )


def ingest_zip(
    archive: Union[bytes, bytearray, BinaryIO],
    destination: Path,
    limits: Optional[IngestionLimits] = None,
    original_filename: Optional[str] = None,
) -> IngestedProject:
    """Extract a ZIP into *destination* after validating every member."""

    configured = limits or IngestionLimits()
    if isinstance(archive, (bytes, bytearray)):
        stream: BinaryIO = io.BytesIO(bytes(archive))
    else:
        stream = archive
    destination = destination.resolve()
    if destination.exists():
        raise IngestionError("destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    total_size = 0
    files: List[str] = []
    try:
        with zipfile.ZipFile(stream) as zipped:
            members = zipped.infolist()
            if len(members) > configured.max_members:
                raise ArchiveLimitError("archive contains too many members")
            destination.mkdir(parents=True, exist_ok=False)
            for member in members:
                if member.is_dir() or member.filename.endswith(("/", "\\")):
                    continue
                path = _safe_member_path(member.filename)
                if any(part in IGNORED_DIRECTORIES for part in path.parts):
                    continue
                mode = (member.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise UnsafeArchiveError("symlinks are not allowed in ZIP archives")
                if member.file_size < 0 or member.file_size > configured.max_member_bytes:
                    raise ArchiveLimitError("archive member exceeds the configured size limit")
                total_size += member.file_size
                if total_size > configured.max_uncompressed_bytes:
                    raise ArchiveLimitError("archive exceeds the configured uncompressed size limit")
                target = destination / path
                _ensure_inside(destination, target)
                target.parent.mkdir(parents=True, exist_ok=True)
                copied = 0
                with zipped.open(member, "r") as source, target.open("wb") as output:
                    while True:
                        chunk = source.read(64 * 1024)
                        if not chunk:
                            break
                        copied += len(chunk)
                        if copied > configured.max_member_bytes:
                            raise ArchiveLimitError("archive member exceeds the configured size limit")
                        output.write(chunk)
                files.append(path.as_posix())
        metadata, traceback = _metadata_and_traceback(destination)
        return IngestedProject(
            root=destination,
            source_type="upload",
            original_filename=original_filename,
            traceback=traceback,
            metadata=metadata,
            files=files,
        )
    except zipfile.BadZipFile as exc:
        shutil.rmtree(str(destination), ignore_errors=True)
        raise IngestionError("uploaded file is not a valid ZIP archive") from exc
    except Exception:
        shutil.rmtree(str(destination), ignore_errors=True)
        raise


def ingestion_limits_from_settings(settings: object) -> IngestionLimits:
    return IngestionLimits(
        max_members=int(getattr(settings, "max_archive_members")),
        max_uncompressed_bytes=int(getattr(settings, "max_archive_uncompressed_bytes")),
        max_member_bytes=int(getattr(settings, "max_archive_member_bytes")),
        max_source_file_bytes=int(getattr(settings, "max_source_file_bytes")),
    )
