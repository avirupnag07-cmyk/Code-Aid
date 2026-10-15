"""Generate and validate small pytest reproductions without executing them."""

import ast
import json
import re
from textwrap import dedent
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .traceback_parser import TracebackInfo


_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SAFE_MODULE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_SAFE_EXCEPTIONS = {
    "AssertionError",
    "AttributeError",
    "IndexError",
    "KeyError",
    "NameError",
    "TypeError",
    "UnboundLocalError",
    "ValueError",
    "ZeroDivisionError",
}


def _python_literal(value: Any) -> Optional[str]:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return repr(value)
    if isinstance(value, str) and len(value) <= 400:
        return repr(value)
    if isinstance(value, list) and len(value) <= 30:
        values = [_python_literal(item) for item in value]
        return "[{}]".format(", ".join(item for item in values if item is not None)) if all(item is not None for item in values) else None
    if isinstance(value, dict) and len(value) <= 30:
        pairs = []
        for key, item in value.items():
            key_literal = _python_literal(key)
            value_literal = _python_literal(item)
            if key_literal is None or value_literal is None:
                return None
            pairs.append("{}: {}".format(key_literal, value_literal))
        return "{{{}}}".format(", ".join(pairs))
    return None


def _module_from_metadata(metadata: Mapping[str, Any]) -> Optional[str]:
    value = metadata.get("module") or metadata.get("entry_module")
    if not value:
        entry_file = metadata.get("entry_file")
        if isinstance(entry_file, str):
            value = entry_file.replace("\\", "/").removesuffix(".py").replace("/", ".")
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if _SAFE_MODULE.fullmatch(value) else None


def _function_from_metadata(spec: Mapping[str, Any], metadata: Mapping[str, Any]) -> Optional[str]:
    value = spec.get("function") or metadata.get("target_function") or metadata.get("function")
    return value if isinstance(value, str) and _SAFE_NAME.fullmatch(value) else None


def _reproduction_test(traceback_info: TracebackInfo, metadata: Mapping[str, Any]) -> str:
    spec_value = metadata.get("test_spec")
    spec: Mapping[str, Any] = spec_value if isinstance(spec_value, Mapping) else {}
    module = _module_from_metadata(metadata)
    function = _function_from_metadata(spec, metadata)
    expected = spec.get("raises") or traceback_info.exception_type
    has_expected_value = "expected" in spec
    expected_value = _python_literal(spec.get("expected")) if has_expected_value else None
    if not isinstance(expected, str) or expected not in _SAFE_EXCEPTIONS:
        expected = "Exception"
    args_value = spec.get("args", [])
    kwargs_value = spec.get("kwargs", {})
    args = _python_literal(args_value) if isinstance(args_value, list) else "[]"
    kwargs = _python_literal(kwargs_value) if isinstance(kwargs_value, dict) else "{}"
    if module and function and args is not None and kwargs is not None:
        call = "{}({})".format(function, ", ".join(["*{}".format(args), "**{}".format(kwargs)]))
        # Explicit import syntax makes the generated test easy to inspect and
        # keeps user-provided strings out of executable source except as literals.
        if has_expected_value and expected_value is not None:
            return dedent(
                """
                import pytest
                from {module} import {function}


                def test_expected_behavior_for_reported_input():
                    assert {call} == {expected_value}
                """.format(module=module, function=function, call=call, expected_value=expected_value)
            ).lstrip()
        return dedent(
            """
            import pytest
            from {module} import {function}


            def test_reproduces_reported_failure():
                with pytest.raises({expected}):
                    {call}
            """.format(module=module, function=function, expected=expected, call=call)
        ).lstrip()
    return dedent(
        """
        import pytest


        def test_reproduces_reported_failure():
            pytest.skip({reason})
        """.format(
            reason=repr(
                "No safe test_spec was bundled for this project; reproduce {} around the innermost frame.".format(
                    traceback_info.exception_type
                )
            )
        )
    ).lstrip()


def validate_test_content(path: str, content: str) -> Dict[str, str]:
    """Validate generated pytest source syntactically and structurally."""

    normalized = path.replace("\\", "/")
    parts = normalized.split("/")
    if not normalized or normalized.startswith("/") or ".." in parts or not normalized.startswith("generated_tests/"):
        return {"status": "invalid", "message": "generated test path is outside generated_tests/"}
    if not normalized.endswith(".py"):
        return {"status": "invalid", "message": "generated test must be a Python file"}
    if "\x00" in content or len(content.encode("utf-8")) > 512 * 1024:
        return {"status": "invalid", "message": "generated test content is invalid or too large"}
    try:
        tree = ast.parse(content, filename=normalized)
    except SyntaxError as exc:
        return {"status": "invalid", "message": "syntax error at line {}".format(exc.lineno or "?")}
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not any(node.name.startswith("test_") for node in functions):
        return {"status": "invalid", "message": "generated test has no test_ function"}
    if not any(isinstance(node, ast.Import) and any(alias.name == "pytest" for alias in node.names) for node in tree.body):
        return {"status": "invalid", "message": "generated test must import pytest"}
    return {"status": "valid", "message": "pytest source parsed successfully"}


def generate_tests(
    traceback_info: TracebackInfo,
    metadata: Optional[Mapping[str, Any]] = None,
    findings: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    metadata = metadata or {}
    content = _reproduction_test(traceback_info, metadata)
    path = "generated_tests/test_code_aid_reproduction.py"
    validation = validate_test_content(path, content)
    spec_value = metadata.get("test_spec")
    spec = spec_value if isinstance(spec_value, Mapping) else {}
    test_mode = "expected-output" if "expected" in spec else "exception-reproduction"
    return [
        {
            "path": path,
            "content": content,
            "purpose": "Reproduce the reported {} in a focused pytest case.".format(traceback_info.exception_type),
            "validation_status": validation["status"],
            "validation_message": validation["message"],
            "test_mode": test_mode,
        }
    ]


def validate_generated_tests(tests: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Return copies with validation fields refreshed for persistence."""

    validated: List[Dict[str, Any]] = []
    for test in tests:
        item = dict(test)
        result = validate_test_content(str(item.get("path") or ""), str(item.get("content") or ""))
        item["validation_status"] = result["status"]
        item["validation_message"] = result["message"]
        validated.append(item)
    return validated
