"""Safe, bounded syntax analysis for the supported source languages.

Adapters in this module only invoke compiler/parser *check* modes.  They never
import, execute, or run a project's programs.  Every adapter has the same
registry boundary so toolchain availability and diagnostic shapes stay
consistent as languages are added.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


MAX_DIAGNOSTIC_OUTPUT = 32 * 1024
DEFAULT_MAX_FILES = 200
DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class Toolchain:
    """A detected executable used by one language adapter."""

    command: str
    path: Optional[str]
    available: bool
    reason: str


@dataclass(frozen=True)
class LanguageDiagnostic:
    language: str
    path: str
    line: Optional[int]
    column: Optional[int]
    severity: str
    message: str
    tool: str
    code: str = ""
    source: str = "adapter"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "severity": self.severity,
            "message": self.message,
            "tool": self.tool,
            "code": self.code,
            "source": self.source,
        }


@dataclass
class LanguageAnalysis:
    detected_languages: List[str] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    analyzed_files: List[str] = field(default_factory=list)
    toolchains: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.detected_languages[0] if self.detected_languages else None,
            "detected_languages": self.detected_languages,
            "diagnostics": self.diagnostics,
            "analyzed_files": self.analyzed_files,
            "toolchains": self.toolchains,
        }


def _toolchain(command: str) -> Toolchain:
    path = shutil.which(command)
    if path:
        return Toolchain(command, path, True, "detected at {}".format(path))
    return Toolchain(command, None, False, "{} is not installed or not on PATH".format(command))


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _diagnostic(
    language: str,
    path: str,
    message: str,
    *,
    line: Optional[int] = None,
    column: Optional[int] = None,
    severity: str = "error",
    tool: str,
    code: str = "",
    source: str = "adapter",
) -> Dict[str, Any]:
    return LanguageDiagnostic(
        language=language,
        path=path,
        line=line,
        column=column,
        severity=severity,
        message=message.strip() or "Language tool reported a diagnostic.",
        tool=tool,
        code=code,
        source=source,
    ).to_dict()


_LOCATION_PATTERNS = (
    # TypeScript's file(line,column), followed by compiler output.
    re.compile(r"^(?P<path>.+?)\((?P<line>\d+),(?P<column>\d+)\):\s*(?P<rest>.*)$"),
    # gcc, javac, go, rustc short output, and node locations.
    re.compile(r"^(?P<path>.+?):(?P<line>\d+)(?::(?P<column>\d+))?:\s*(?P<rest>.*)$"),
    re.compile(r"^(?P<path>.+?):(?P<line>\d+)\s+(?P<rest>.*)$"),
)
_LINE_ONLY_PATTERN = re.compile(r"^(?P<path>.+?):(?P<line>\d+)$")


def normalize_diagnostics(
    language: str,
    output: str,
    path: str,
    tool: str,
) -> List[Dict[str, Any]]:
    """Normalize native tool output into the API diagnostic contract."""

    diagnostics: List[Dict[str, Any]] = []
    pending_index: Optional[int] = None
    pending_location: Optional[Tuple[str, int, Optional[int]]] = None
    for raw_line in output[:MAX_DIAGNOSTIC_OUTPUT].splitlines():
        line_text = raw_line.strip()
        if not line_text or line_text in {"^", "|"}:
            continue
        if re.match(r"^(?:\d+\s+\||\|\s*|[\s|~^]+$)", line_text):
            continue
        if line_text.startswith(("at ", "Node.js v")) or re.match(r"^\d+ errors? generated\.?$", line_text):
            continue
        rust_location = re.match(r"^-->\s+(?P<path>.+?):(?P<line>\d+):(?P<column>\d+)$", line_text)
        if rust_location and pending_index is not None:
            item = diagnostics[pending_index]
            item["path"] = rust_location.group("path")
            item["line"] = int(rust_location.group("line"))
            item["column"] = int(rust_location.group("column"))
            pending_index = None
            continue
        line_only = _LINE_ONLY_PATTERN.match(line_text)
        if line_only and not line_only.group("path").startswith(("http", "error", "warning")):
            pending_location = (line_only.group("path"), int(line_only.group("line")), None)
            continue
        location: Optional[re.Match[str]] = None
        for pattern in _LOCATION_PATTERNS:
            location = pattern.match(line_text)
            if location:
                break
        if location:
            groups = location.groupdict()
            message = groups.get("rest", "")
            actual_path = groups.get("path") or path
            line_number = int(groups["line"]) if groups.get("line") else None
            column_number = int(groups["column"]) if groups.get("column") else None
        else:
            actual_path = path
            line_number = None
            column_number = None
            message = line_text
        lowered = message.lower()
        severity = "warning" if "warning" in lowered else "info" if "note" in lowered else "error"
        code_match = re.search(r"\b(?:TS\d+|[A-Za-z]+\.(?:err|warn)\.[A-Za-z0-9_.-]+)\b", message)
        code = code_match.group(0) if code_match else ""
        # Rust emits a separate "error[...]" line and a location arrow.  Keep
        # the normalized message while allowing the next line to supply a
        # useful location when the native format has one.
        if actual_path.startswith("error") and "-->" in line_text:
            continue
        if pending_location and line_number is None and (
            "syntaxerror" in lowered or line_text.startswith(("error", "warning"))
        ):
            actual_path, line_number, column_number = pending_location
            pending_location = None
        elif pending_location and line_number is None:
            # Node prints the offending source line between its location and
            # the actual SyntaxError; it is context, not a second diagnostic.
            continue
        diagnostics.append(
            _diagnostic(
                language,
                actual_path,
                message,
                line=line_number,
                column=column_number,
                severity=severity,
                tool=tool,
                code=code,
            )
        )
        if line_text.startswith(("error", "warning")):
            pending_index = len(diagnostics) - 1
    return diagnostics


def _run_check(command: Sequence[str], cwd: Path, timeout_seconds: float) -> Tuple[str, str, Optional[int], str]:
    """Run a parser/compiler check with strict resource and output bounds."""

    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            start_new_session=True,
        )
    except subprocess.TimeoutExpired as exc:
        return "", str(exc), None, "timeout"
    except OSError as exc:
        return "", str(exc), None, "error"
    stdout = (completed.stdout or "")[:MAX_DIAGNOSTIC_OUTPUT]
    stderr = (completed.stderr or "")[:MAX_DIAGNOSTIC_OUTPUT]
    return stdout, stderr, completed.returncode, "completed"


class LanguageAdapter:
    language_id = ""
    name = ""
    extensions: Tuple[str, ...] = ()
    tool_name = ""

    def __init__(self) -> None:
        self.toolchain = _toolchain(self.tool_name) if self.tool_name else Toolchain("ast", None, True, "Python ast is part of the runtime")

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def matrix_entry(self) -> Dict[str, Any]:
        analysis_status = "supported" if self.toolchain.available else "unavailable"
        test_generation = "pytest-template" if self.language_id == "python" else "not-configured"
        execution = "docker-isolated" if self.language_id == "python" else "not-configured"
        return {
            "id": self.language_id,
            "name": self.name,
            "extensions": list(self.extensions),
            "status": analysis_status,
            "detection": "supported",
            "syntax": analysis_status,
            "analysis": analysis_status,
            "diagnostics": analysis_status,
            "test_generation": test_generation,
            "execution": execution,
            "notes": self.toolchain.reason,
            "tool": self.toolchain.command,
            "available": self.toolchain.available,
            "reason": self.toolchain.reason,
        }

    def unavailable(self, path: str) -> Dict[str, Any]:
        return _diagnostic(
            self.language_id,
            path,
            "{} analysis is unavailable: {}".format(self.name, self.toolchain.reason),
            severity="info",
            tool=self.toolchain.command,
            code="tool-unavailable",
            source="toolchain",
        )

    def analyze_file(self, root: Path, path: Path, timeout_seconds: float) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def analyze(self, root: Path, files: Sequence[Path], timeout_seconds: float) -> Tuple[List[Dict[str, Any]], List[str]]:
        diagnostics: List[Dict[str, Any]] = []
        analyzed: List[str] = []
        for path in files:
            relative = _relative(root, path)
            if not self.toolchain.available:
                diagnostics.append(self.unavailable(relative))
                continue
            diagnostics.extend(self.analyze_file(root, path, timeout_seconds))
            analyzed.append(relative)
        return diagnostics, analyzed


class PythonAdapter(LanguageAdapter):
    language_id = "python"
    name = "Python"
    extensions = (".py",)

    def analyze_file(self, root: Path, path: Path, timeout_seconds: float) -> List[Dict[str, Any]]:
        relative = _relative(root, path)
        try:
            ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=relative)
        except SyntaxError as exc:
            return [
                _diagnostic(
                    self.language_id,
                    relative,
                    "Python syntax error: {}".format(exc.msg),
                    line=exc.lineno,
                    column=exc.offset,
                    tool="ast",
                    code="syntax-error",
                )
            ]
        except (OSError, UnicodeError) as exc:
            return [_diagnostic(self.language_id, relative, "Unable to read source: {}".format(exc), tool="ast")]
        return []


class NativeAdapter(LanguageAdapter):
    command_prefix: Tuple[str, ...] = ()

    def analyze_file(self, root: Path, path: Path, timeout_seconds: float) -> List[Dict[str, Any]]:
        relative = _relative(root, path)
        stdout, stderr, returncode, status = _run_check(
            (*self.command_prefix, str(path)), root, timeout_seconds
        )
        output = "\n".join(part for part in (stderr, stdout) if part)
        if status == "timeout":
            return [_diagnostic(self.language_id, relative, "{} analysis timed out.".format(self.name), severity="warning", tool=self.tool_name, code="tool-timeout", source="toolchain")]
        if status == "error":
            return [_diagnostic(self.language_id, relative, "{} analysis failed to start: {}".format(self.name, stderr), tool=self.tool_name, code="tool-error", source="toolchain")]
        if returncode and not output:
            output = "{} exited with status {}".format(self.tool_name, returncode)
        diagnostics = normalize_diagnostics(self.language_id, output, relative, self.tool_name) if output else []
        for item in diagnostics:
            candidate = Path(str(item.get("path") or ""))
            if candidate.is_absolute():
                item["path"] = _relative(root, candidate)
        return diagnostics


class JavaScriptAdapter(NativeAdapter):
    language_id = "javascript"
    name = "JavaScript"
    extensions = (".js", ".jsx", ".mjs", ".cjs")
    tool_name = "node"

    def analyze_file(self, root: Path, path: Path, timeout_seconds: float) -> List[Dict[str, Any]]:
        self.command_prefix = (self.toolchain.path or self.tool_name, "--check")
        return super().analyze_file(root, path, timeout_seconds)


class TypeScriptAdapter(NativeAdapter):
    language_id = "typescript"
    name = "TypeScript"
    extensions = (".ts", ".tsx", ".mts", ".cts")
    tool_name = "tsc"

    def analyze_file(self, root: Path, path: Path, timeout_seconds: float) -> List[Dict[str, Any]]:
        self.command_prefix = (
            self.toolchain.path or self.tool_name,
            "--noEmit",
            "--pretty",
            "false",
            "--skipLibCheck",
        )
        return super().analyze_file(root, path, timeout_seconds)


class JavaAdapter(NativeAdapter):
    language_id = "java"
    name = "Java"
    extensions = (".java",)
    tool_name = "javac"

    def analyze_file(self, root: Path, path: Path, timeout_seconds: float) -> List[Dict[str, Any]]:
        with tempfile.TemporaryDirectory(prefix="code-aid-javac-") as output_dir:
            self.command_prefix = (
                self.toolchain.path or self.tool_name,
                "-proc:none",
                "-XDrawDiagnostics",
                "-d",
                output_dir,
            )
            return super().analyze_file(root, path, timeout_seconds)


class CAdapter(NativeAdapter):
    language_id = "c"
    name = "C"
    extensions = (".c", ".h")
    tool_name = "gcc"

    def analyze_file(self, root: Path, path: Path, timeout_seconds: float) -> List[Dict[str, Any]]:
        self.command_prefix = (self.toolchain.path or self.tool_name, "-fsyntax-only", "-x", "c")
        return super().analyze_file(root, path, timeout_seconds)


class CppAdapter(NativeAdapter):
    language_id = "cpp"
    name = "C++"
    extensions = (".cc", ".cp", ".cpp", ".cxx", ".hh", ".hpp", ".hxx")
    tool_name = "g++"

    def analyze_file(self, root: Path, path: Path, timeout_seconds: float) -> List[Dict[str, Any]]:
        self.command_prefix = (self.toolchain.path or self.tool_name, "-fsyntax-only", "-x", "c++")
        return super().analyze_file(root, path, timeout_seconds)


class GoAdapter(NativeAdapter):
    language_id = "go"
    name = "Go"
    extensions = (".go",)
    tool_name = "go"

    def analyze_file(self, root: Path, path: Path, timeout_seconds: float) -> List[Dict[str, Any]]:
        # go tool compile checks syntax/types without starting a test or binary.
        with tempfile.TemporaryDirectory(prefix="code-aid-go-") as output_dir:
            self.command_prefix = (
                self.toolchain.path or self.tool_name,
                "tool",
                "compile",
                "-e",
                "-o",
                str(Path(output_dir) / "source.o"),
            )
            return super().analyze_file(root, path, timeout_seconds)


class RustAdapter(NativeAdapter):
    language_id = "rust"
    name = "Rust"
    extensions = (".rs",)
    tool_name = "cargo"

    def __init__(self) -> None:
        cargo = _toolchain("cargo")
        rustc = _toolchain("rustc")
        # Cargo without rustc is not a usable analysis toolchain. Reporting it
        # as available would turn a later cargo failure into a misleading
        # support claim. Standalone sources use rustc; Cargo projects use both.
        if cargo.available and rustc.available:
            self.toolchain = cargo
        elif rustc.available:
            self.toolchain = rustc
        else:
            self.toolchain = Toolchain(
                "cargo/rustc",
                None,
                False,
                "Rust analysis requires both cargo and rustc",
            )
        self.tool_name = self.toolchain.command

    def analyze(self, root: Path, files: Sequence[Path], timeout_seconds: float) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Prefer cargo check for real Cargo projects, without running binaries."""

        manifest = root / "Cargo.toml"
        if self.toolchain.available and self.toolchain.command == "cargo" and manifest.is_file():
            with tempfile.TemporaryDirectory(prefix="code-aid-cargo-") as target_dir:
                stdout, stderr, returncode, status = _run_check(
                    (
                        self.toolchain.path or self.tool_name,
                        "check",
                        "--offline",
                        "--message-format=short",
                        "--target-dir",
                        target_dir,
                        "--manifest-path",
                        str(manifest),
                    ),
                    root,
                    timeout_seconds,
                )
            output = "\n".join(part for part in (stderr, stdout) if part)
            if status == "timeout":
                return [self.unavailable("Cargo.toml") | {"severity": "warning", "message": "Rust cargo check timed out.", "code": "tool-timeout"}], []
            if status == "error":
                return [self.unavailable("Cargo.toml") | {"severity": "error", "message": "Rust cargo check failed to start.", "code": "tool-error"}], []
            diagnostics = normalize_diagnostics(self.language_id, output, "Cargo.toml", self.tool_name) if output else []
            for item in diagnostics:
                candidate = Path(str(item.get("path") or ""))
                if candidate.is_absolute():
                    item["path"] = _relative(root, candidate)
            return diagnostics, [_relative(root, path) for path in files]
        return super().analyze(root, files, timeout_seconds)

    def analyze_file(self, root: Path, path: Path, timeout_seconds: float) -> List[Dict[str, Any]]:
        # rustc metadata emission is a parse/type check and never runs the crate.
        rustc = shutil.which("rustc")
        if rustc:
            with tempfile.TemporaryDirectory(prefix="code-aid-rust-") as output_dir:
                self.command_prefix = (
                    rustc,
                    "--emit",
                    "metadata",
                    "--crate-type",
                    "lib",
                    "-o",
                    str(Path(output_dir) / "source.rmeta"),
                )
                return super().analyze_file(root, path, timeout_seconds)
        else:
            self.command_prefix = (self.toolchain.path or self.tool_name, "check", "--offline")
        return super().analyze_file(root, path, timeout_seconds)


class AdapterRegistry:
    """Registry and orchestration boundary shared by all language adapters."""

    def __init__(self, adapters: Optional[Iterable[LanguageAdapter]] = None) -> None:
        configured = list(adapters) if adapters is not None else [
            PythonAdapter(),
            JavaScriptAdapter(),
            TypeScriptAdapter(),
            JavaAdapter(),
            CAdapter(),
            CppAdapter(),
            GoAdapter(),
            RustAdapter(),
        ]
        self._adapters: Dict[str, LanguageAdapter] = {adapter.language_id: adapter for adapter in configured}

    def register(self, adapter: LanguageAdapter) -> None:
        self._adapters[adapter.language_id] = adapter

    def get(self, language_id: str) -> Optional[LanguageAdapter]:
        return self._adapters.get(language_id)

    def adapters(self) -> List[LanguageAdapter]:
        return list(self._adapters.values())

    def detect(self, root: Path, max_files: int = DEFAULT_MAX_FILES) -> Dict[str, List[Path]]:
        detected: Dict[str, List[Path]] = {adapter.language_id: [] for adapter in self.adapters()}
        paths = (path for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()) if path.is_file() and not path.is_symlink() and ".git" not in path.parts)
        count = 0
        for path in paths:
            if count >= max_files:
                break
            for adapter in self.adapters():
                if adapter.supports(path):
                    detected[adapter.language_id].append(path)
                    count += 1
                    break
        return {key: value for key, value in detected.items() if value}

    def support_matrix(self) -> List[Dict[str, Any]]:
        return [adapter.matrix_entry() for adapter in self.adapters()]

    def analyze(
        self,
        root: Path,
        *,
        max_source_file_bytes: int = 512 * 1024,
        max_files: int = DEFAULT_MAX_FILES,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> LanguageAnalysis:
        detected = self.detect(root, max_files=max_files)
        result = LanguageAnalysis(detected_languages=sorted(detected))
        for adapter in self.adapters():
            paths = detected.get(adapter.language_id, [])
            if not paths:
                continue
            bounded = []
            for path in paths:
                try:
                    if path.stat().st_size <= max_source_file_bytes:
                        bounded.append(path)
                    else:
                        result.diagnostics.append(_diagnostic(adapter.language_id, _relative(root, path), "Source file was skipped because it exceeds the analysis size limit.", severity="info", tool=adapter.toolchain.command, code="source-size-limit", source="limits"))
                except OSError as exc:
                    result.diagnostics.append(_diagnostic(adapter.language_id, _relative(root, path), "Source file could not be read: {}".format(exc), tool=adapter.toolchain.command, code="source-read-error", source="limits"))
            diagnostics, analyzed = adapter.analyze(root, bounded, timeout_seconds)
            result.diagnostics.extend(diagnostics)
            result.analyzed_files.extend(analyzed)
            result.toolchains[adapter.language_id] = adapter.matrix_entry()
        return result


_DEFAULT_REGISTRY = AdapterRegistry()


def get_default_registry() -> AdapterRegistry:
    return _DEFAULT_REGISTRY


def detect_languages(project_root: Path, registry: Optional[AdapterRegistry] = None) -> List[str]:
    return sorted((registry or _DEFAULT_REGISTRY).detect(project_root))


def analyze_project_languages(project_root: Path, **kwargs: Any) -> LanguageAnalysis:
    return (kwargs.pop("registry", None) or _DEFAULT_REGISTRY).analyze(project_root, **kwargs)


def language_support_matrix(registry: Optional[AdapterRegistry] = None) -> List[Dict[str, Any]]:
    return (registry or _DEFAULT_REGISTRY).support_matrix()
