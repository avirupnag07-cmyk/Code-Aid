"""Non-mutating verification of proposed source-file changes."""

import ast
import difflib
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Mapping, Optional


class PatchVerificationError(ValueError):
    """Raised for an unsafe file path or malformed patch input."""


def _relative_path(value: str) -> Path:
    if not value or "\x00" in value:
        raise PatchVerificationError("file_path must be a non-empty relative path")
    normalized = value.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if normalized.startswith("/") or any(part in ("..", "") for part in pure.parts) or ":" in pure.parts[0]:
        raise PatchVerificationError("file_path must stay inside the investigation project")
    return Path(*pure.parts)


def _inside(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise PatchVerificationError("file_path escapes the investigation project") from exc
    current = target.parent
    while current != root and current != current.parent:
        if current.is_symlink():
            raise PatchVerificationError("file_path traverses a symlink")
        current = current.parent


def _check(name: str, status: str, message: str, evidence: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {"name": name, "status": status, "message": message, "evidence": evidence or []}


def verify_patch(
    project_root: Path,
    file_path: str,
    proposed_content: str,
    *,
    max_bytes: int = 512 * 1024,
) -> Dict[str, Any]:
    """Verify a proposed patch without writing it into the original project."""

    relative = _relative_path(file_path)
    root = project_root.resolve()
    if not root.is_dir():
        raise PatchVerificationError("investigation project is unavailable")
    target = root / relative
    _inside(root, target)
    if not isinstance(proposed_content, str):
        raise PatchVerificationError("content must be text")
    if "\x00" in proposed_content:
        raise PatchVerificationError("content cannot contain NUL bytes")
    if len(proposed_content.encode("utf-8")) > max_bytes:
        raise PatchVerificationError("proposed content exceeds the size limit")
    if target.exists() and (target.is_symlink() or not target.is_file()):
        raise PatchVerificationError("target is not a regular file")
    original = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
    changed = original != proposed_content
    checks: List[Dict[str, Any]] = [
        _check("path-safety", "passed", "The proposed path is relative and remains inside the project."),
        _check("size-limit", "passed", "The proposed file is within the configured size limit."),
        _check("change-detection", "passed" if changed else "warning", "File content differs from the current project." if changed else "Proposed content is identical to the current file."),
    ]
    syntax_valid: Optional[bool] = None
    if relative.suffix.lower() == ".py":
        try:
            ast.parse(proposed_content, filename=relative.as_posix())
        except SyntaxError as exc:
            syntax_valid = False
            evidence = [{"file": relative.as_posix(), "line": exc.lineno, "snippet": "", "reason": "Python parser error"}]
            checks.append(_check("python-syntax", "failed", "The proposed Python file has a syntax error.", evidence))
        else:
            syntax_valid = True
            checks.append(_check("python-syntax", "passed", "The proposed Python file parses successfully."))

    diff_lines = difflib.unified_diff(
        original.splitlines(),
        proposed_content.splitlines(),
        fromfile="a/{}".format(relative.as_posix()),
        tofile="b/{}".format(relative.as_posix()),
        lineterm="",
    )
    diff = "\n".join(diff_lines)
    failed = any(item["status"] == "failed" for item in checks)
    status = "invalid" if failed else ("verified" if changed else "no-change")
    return {
        "status": status,
        "file_path": relative.as_posix(),
        "changed": changed,
        "safe_to_apply": not failed and changed,
        "syntax_valid": syntax_valid,
        "diff": diff[:100_000],
        "message": "Proposed change passed non-executing verification." if not failed else "Proposed change failed verification.",
        "checks": checks,
    }


verify_proposed_change = verify_patch
