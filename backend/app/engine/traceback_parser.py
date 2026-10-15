"""Parser for Python traceback text used as deterministic investigation input."""

from dataclasses import dataclass, asdict
import re
from typing import Dict, List, Optional


SUPPORTED_EXCEPTION_TYPES = {
    "AssertionError",
    "AttributeError",
    "FileNotFoundError",
    "ImportError",
    "IndexError",
    "KeyError",
    "ModuleNotFoundError",
    "NameError",
    "OverflowError",
    "RuntimeError",
    "SyntaxError",
    "TypeError",
    "UnboundLocalError",
    "ValueError",
    "ZeroDivisionError",
}


class TracebackParseError(ValueError):
    """Raised when input does not contain a recognizable Python exception."""


@dataclass(frozen=True)
class TracebackFrame:
    file: str
    line: int
    function: str = "<module>"
    code: str = ""

    @property
    def evidence(self) -> Dict[str, object]:
        return {
            "file": self.file,
            "line": self.line,
            "snippet": self.code,
            "reason": "reported traceback frame",
        }


@dataclass(frozen=True)
class TracebackInfo:
    exception_type: str
    message: str
    frames: List[TracebackFrame]
    raw_text: str
    final_line: str

    @property
    def supported(self) -> bool:
        return self.exception_type in SUPPORTED_EXCEPTION_TYPES

    @property
    def innermost_frame(self) -> Optional[TracebackFrame]:
        return self.frames[-1] if self.frames else None

    def to_dict(self) -> Dict[str, object]:
        return {
            "exception_type": self.exception_type,
            "message": self.message,
            "frames": [asdict(frame) for frame in self.frames],
            "raw_text": self.raw_text,
            "final_line": self.final_line,
            "supported": self.supported,
        }


_FRAME_RE = re.compile(
    r'^\s*File\s+["\'](?P<file>.+?)["\'],\s+line\s+(?P<line>\d+)(?:,\s+in\s+(?P<function>.*?))?\s*$'
)
_EXCEPTION_RE = re.compile(
    r'^\s*(?:[A-Za-z]:\s*)?(?P<type>[A-Za-z_][\w.]*(?:Error|Exception|Warning|Interrupt|Exit))'
    r'(?:\s*:\s*(?P<message>.*))?\s*$'
)


def _normal_exception_name(value: str) -> str:
    return value.rsplit(".", 1)[-1]


def parse_traceback(text: str, max_chars: int = 100_000) -> TracebackInfo:
    """Parse frames and the final exception without importing user code."""

    if not isinstance(text, str) or not text.strip():
        raise TracebackParseError("traceback must be a non-empty string")
    if len(text) > max_chars:
        raise TracebackParseError("traceback exceeds the configured size limit")

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    frames: List[TracebackFrame] = []
    for index, line in enumerate(lines):
        match = _FRAME_RE.match(line)
        if not match:
            continue
        code = ""
        if index + 1 < len(lines):
            candidate = lines[index + 1].strip()
            if candidate and not _FRAME_RE.match(lines[index + 1]):
                code = candidate
        frames.append(
            TracebackFrame(
                file=match.group("file"),
                line=int(match.group("line")),
                function=(match.group("function") or "<module>").strip(),
                code=code,
            )
        )

    final_line = ""
    exception_type = ""
    message = ""
    for line in reversed(lines):
        candidate = line.strip()
        if not candidate:
            continue
        # Pytest prefixes traceback exception lines with ``E ``.
        candidate = re.sub(r"^E\s+", "", candidate)
        match = _EXCEPTION_RE.match(candidate)
        if match:
            final_line = candidate
            exception_type = _normal_exception_name(match.group("type"))
            message = (match.group("message") or "").strip()
            break
    if not exception_type:
        raise TracebackParseError("traceback does not end with a recognizable Python exception")
    return TracebackInfo(
        exception_type=exception_type,
        message=message,
        frames=frames,
        raw_text=text,
        final_line=final_line,
    )


# Compatibility-friendly name for callers that prefer a verb phrase.
parse_python_traceback = parse_traceback
