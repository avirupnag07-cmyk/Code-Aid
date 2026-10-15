"""AST-based static analysis with line-level evidence.

The analyzer deliberately parses source instead of importing it.  That makes
analysis safe for uploaded projects and keeps its output deterministic.
"""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .traceback_parser import TracebackInfo, TracebackFrame


@dataclass
class AnalysisResult:
    facts: List[Dict[str, Any]]
    findings: List[Dict[str, Any]]
    parsed_files: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {"facts": self.facts, "findings": self.findings, "parsed_files": self.parsed_files}


def _evidence(
    root: Path,
    path: Path,
    line: Optional[int],
    source_lines: Sequence[str],
    reason: str,
    end_line: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        relative = path.name
    snippet = ""
    if line is not None and 1 <= line <= len(source_lines):
        start = max(1, line - 1)
        finish = min(len(source_lines), end_line or line)
        snippet = "\n".join(source_lines[start - 1 : finish]).strip()
    item: Dict[str, Any] = {"file": relative, "line": line, "snippet": snippet, "reason": reason}
    if end_line is not None:
        item["end_line"] = end_line
    return item


def _literal_kind(node: ast.AST) -> Optional[str]:
    if not isinstance(node, ast.Constant):
        return None
    if isinstance(node.value, str):
        return "string"
    if isinstance(node.value, (int, float, complex)) and not isinstance(node.value, bool):
        return "number"
    return type(node.value).__name__


def _frame_path(root: Path, frame: TracebackFrame) -> Optional[Path]:
    raw = frame.file.replace("\\", "/")
    candidate = Path(raw)
    if not candidate.is_absolute():
        direct = root / candidate
        if direct.is_file():
            return direct
    else:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root.resolve())
            if resolved.is_file():
                return resolved
        except (OSError, ValueError):
            pass
    name = Path(raw).name
    matches = [path for path in root.rglob(name) if path.is_file() and not path.is_symlink()]
    if not matches:
        return None
    # Prefer a suffix match for tracebacks containing a project-relative prefix.
    raw_parts = tuple(part for part in Path(raw).parts if part not in (".", ""))
    suffix_matches = [
        path
        for path in matches
        if tuple(path.relative_to(root).parts[-len(raw_parts) :]) == raw_parts[-len(path.relative_to(root).parts) :]
    ]
    return sorted(suffix_matches or matches, key=lambda item: item.as_posix())[0]


def _node_end(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno", getattr(node, "lineno", 1)))


def _node_at_line(tree: ast.AST, line: int) -> Optional[ast.AST]:
    candidates = [
        node
        for node in ast.walk(tree)
        if hasattr(node, "lineno") and int(getattr(node, "lineno")) <= line <= _node_end(node)
    ]
    return sorted(candidates, key=lambda node: (_node_end(node) - int(getattr(node, "lineno")), int(getattr(node, "lineno"))))[0] if candidates else None


def _add_finding(
    findings: List[Dict[str, Any]],
    *,
    text: str,
    severity: str,
    rule_id: str,
    evidence: Dict[str, Any],
) -> None:
    key = (rule_id, evidence.get("file"), evidence.get("line"), text)
    if any(
        (item.get("rule_id"), item.get("evidence", [{}])[0].get("file"), item.get("evidence", [{}])[0].get("line"), item.get("text"))
        == key
        for item in findings
    ):
        return
    findings.append(
        {
            "text": text,
            "severity": severity,
            "rule_id": rule_id,
            "evidence": [evidence],
        }
    )


def _analyze_nodes(
    root: Path,
    path: Path,
    source_lines: Sequence[str],
    tree: ast.AST,
    traceback_info: TracebackInfo,
    findings: List[Dict[str, Any]],
) -> None:
    traceback_frame = next(
        (frame for frame in reversed(traceback_info.frames) if _frame_path(root, frame) == path), None
    )
    for node in ast.walk(tree):
        line = int(getattr(node, "lineno", 1))
        end_line = _node_end(node)
        evidence = _evidence(root, path, line, source_lines, "AST rule match", end_line if end_line != line else None)
        if isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name) and node.type.id == "Exception":
            _add_finding(
                findings,
                text="Broad exception handling can hide the reported failure and make regressions harder to detect.",
                severity="medium",
                rule_id="broad-exception",
                evidence=evidence,
            )
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left_kind = _literal_kind(node.left)
            right_kind = _literal_kind(node.right)
            if {left_kind, right_kind} == {"string", "number"}:
                _add_finding(
                    findings,
                    text="A binary operation combines a string literal with a numeric literal, which is incompatible for this operator.",
                    severity="high",
                    rule_id="mixed-literal-operation",
                    evidence=evidence,
                )
            elif traceback_frame and traceback_frame.line >= line and traceback_frame.line <= end_line and traceback_info.exception_type == "TypeError":
                _add_finding(
                    findings,
                    text="The reported TypeError occurs at a binary operation; operand types should be checked before combining them.",
                    severity="high",
                    rule_id="traceback-binary-operation",
                    evidence=_evidence(root, path, traceback_frame.line, source_lines, "reported TypeError frame"),
                )
        if isinstance(node, ast.Subscript) and traceback_frame and traceback_frame.line >= line and traceback_frame.line <= end_line:
            if traceback_info.exception_type == "KeyError":
                _add_finding(
                    findings,
                    text="The reported KeyError is raised by a mapping lookup that assumes a key is present.",
                    severity="high",
                    rule_id="unchecked-mapping-lookup",
                    evidence=_evidence(root, path, traceback_frame.line, source_lines, "reported KeyError frame"),
                )
            elif traceback_info.exception_type == "IndexError":
                _add_finding(
                    findings,
                    text="The reported IndexError is raised by an unchecked sequence index.",
                    severity="high",
                    rule_id="unchecked-sequence-index",
                    evidence=_evidence(root, path, traceback_frame.line, source_lines, "reported IndexError frame"),
                )
        if isinstance(node, ast.Attribute) and traceback_frame and traceback_frame.line >= line and traceback_frame.line <= end_line and traceback_info.exception_type == "AttributeError":
            _add_finding(
                findings,
                text="The reported AttributeError occurs while accessing an attribute on a value whose runtime type should be validated.",
                severity="high",
                rule_id="unchecked-attribute-access",
                evidence=_evidence(root, path, traceback_frame.line, source_lines, "reported AttributeError frame"),
            )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"int", "float", "decimal"}:
            if traceback_info.exception_type == "ValueError" and traceback_frame and traceback_frame.line >= line and traceback_frame.line <= end_line:
                _add_finding(
                    findings,
                    text="A numeric conversion at the reported frame can raise ValueError for unvalidated input.",
                    severity="high",
                    rule_id="unchecked-numeric-conversion",
                    evidence=_evidence(root, path, traceback_frame.line, source_lines, "reported ValueError frame"),
                )


def analyze_project(
    project_root: Path,
    traceback_info: TracebackInfo,
    metadata: Optional[Dict[str, Any]] = None,
    max_source_file_bytes: int = 512 * 1024,
) -> AnalysisResult:
    """Parse every Python file and produce facts/findings with evidence."""

    root = project_root.resolve()
    if not root.is_dir():
        raise ValueError("project root is not a directory")
    python_files = sorted(
        path
        for path in root.rglob("*.py")
        if path.is_file() and not path.is_symlink() and ".git" not in path.parts
    )
    facts: List[Dict[str, Any]] = [
        {
            "text": "Found {} Python source file(s) in the project.".format(len(python_files)),
            "evidence": [],
        },
        {
            "text": "The traceback reports {}: {}".format(traceback_info.exception_type, traceback_info.message or "(no message)"),
            "evidence": [frame.evidence for frame in traceback_info.frames],
        },
    ]
    if metadata and metadata.get("category"):
        facts.append({"text": "Sample category: {}.".format(metadata["category"]), "evidence": []})
    findings: List[Dict[str, Any]] = []
    parsed_files: List[str] = []
    for path in python_files:
        try:
            source = path.read_bytes()
        except OSError as exc:
            _add_finding(
                findings,
                text="Source file could not be read: {}".format(exc),
                severity="medium",
                rule_id="unreadable-source",
                evidence=_evidence(root, path, None, [], "source read failure"),
            )
            continue
        if len(source) > max_source_file_bytes:
            _add_finding(
                findings,
                text="Source file was skipped because it exceeds the analysis size limit.",
                severity="medium",
                rule_id="source-size-limit",
                evidence=_evidence(root, path, None, [], "source size limit"),
            )
            continue
        text = source.decode("utf-8", errors="replace")
        lines = text.splitlines()
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            _add_finding(
                findings,
                text="Python syntax is invalid in this source file.",
                severity="high",
                rule_id="syntax-error",
                evidence=_evidence(root, path, exc.lineno, lines, "Python parser error"),
            )
            continue
        parsed_files.append(path.relative_to(root).as_posix())
        _analyze_nodes(root, path, lines, tree, traceback_info, findings)

    if traceback_info.frames and not any(_frame_path(root, frame) for frame in traceback_info.frames):
        frame = traceback_info.innermost_frame
        if frame:
            findings.append(
                {
                    "text": "The innermost traceback file was not found in the ingested project.",
                    "severity": "medium",
                    "rule_id": "missing-traceback-file",
                    "evidence": [frame.evidence],
                }
            )
    if not findings:
        findings.append(
            {
                "text": "No deterministic static rule matched the reported failure; inspect the hypotheses and generated tests.",
                "severity": "info",
                "rule_id": "no-static-match",
                "evidence": [frame.evidence for frame in traceback_info.frames[-1:]],
            }
        )
    return AnalysisResult(facts=facts, findings=findings, parsed_files=parsed_files)


# Short alias used by some integrations.
analyze = analyze_project
