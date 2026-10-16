from pathlib import Path

import pytest

from app.engine import language_analysis as language


def test_default_registry_has_all_requested_languages():
    registry = language.AdapterRegistry()
    assert {adapter.language_id for adapter in registry.adapters()} == {
        "python",
        "javascript",
        "typescript",
        "java",
        "c",
        "cpp",
        "go",
        "rust",
    }


def test_detection_is_extension_based_and_bounded(tmp_path):
    (tmp_path / "main.py").write_text("pass\n")
    (tmp_path / "client.ts").write_text("const answer: number = 42\n")
    (tmp_path / "ignored.txt").write_text("not source\n")
    registry = language.AdapterRegistry()
    detected = registry.detect(tmp_path)
    assert [path.name for path in detected["python"]] == ["main.py"]
    assert [path.name for path in detected["typescript"]] == ["client.ts"]
    assert language.detect_languages(tmp_path, registry) == ["python", "typescript"]
    assert sum(len(paths) for paths in registry.detect(tmp_path, max_files=1).values()) == 1


def test_normalization_produces_one_stable_diagnostic_shape():
    diagnostics = language.normalize_diagnostics(
        "c",
        "main.c:4:7: error: expected ';'\nmain.c:8: warning: unused value",
        "main.c",
        "gcc",
    )
    assert diagnostics == [
        {
            "language": "c",
            "path": "main.c",
            "line": 4,
            "column": 7,
            "severity": "error",
            "message": "error: expected ';'",
            "tool": "gcc",
            "code": "",
            "source": "adapter",
        },
        {
            "language": "c",
            "path": "main.c",
            "line": 8,
            "column": None,
            "severity": "warning",
            "message": "warning: unused value",
            "tool": "gcc",
            "code": "",
            "source": "adapter",
        },
    ]


def test_unavailable_toolchain_is_explicit(tmp_path, monkeypatch):
    source = tmp_path / "broken.js"
    source.write_text("const = ;\n")
    monkeypatch.setattr(language.shutil, "which", lambda command: None)
    registry = language.AdapterRegistry()
    result = registry.analyze(tmp_path)
    assert result.detected_languages == ["javascript"]
    assert result.diagnostics[0]["code"] == "tool-unavailable"
    assert "not installed" in result.diagnostics[0]["message"]


@pytest.mark.parametrize(
    ("adapter_class", "filename", "source"),
    [
        (language.PythonAdapter, "source.py", "def ok():\n    return 1\n"),
        (language.JavaScriptAdapter, "source.js", "const answer = 42;\n"),
        (language.TypeScriptAdapter, "source.ts", "const answer: number = 42;\n"),
        (language.JavaAdapter, "Source.java", "class Source { int answer() { return 42; } }\n"),
        (language.CAdapter, "source.c", "int answer(void) { return 42; }\n"),
        (language.CppAdapter, "source.cpp", "int answer() { return 42; }\n"),
        (language.GoAdapter, "source.go", "package source\nfunc answer() int { return 42 }\n"),
        (language.RustAdapter, "source.rs", "fn answer() -> i32 { 42 }\n"),
    ],
)
def test_each_adapter_has_a_safe_parsing_path(tmp_path, monkeypatch, adapter_class, filename, source):
    path = tmp_path / filename
    path.write_text(source)
    adapter = adapter_class()
    adapter.toolchain = language.Toolchain(adapter.tool_name or "ast", "/tool", True, "test tool")

    if adapter.language_id != "python":
        calls = []

        def fake_run(command, cwd, timeout_seconds):
            calls.append(list(command))
            return "", "", 0, "completed"

        monkeypatch.setattr(language, "_run_check", fake_run)
    else:
        calls = []
    result = adapter.analyze_file(tmp_path, path, 1.0)
    assert result == []
    if adapter.language_id != "python":
        assert calls
        assert str(path) in calls[0]


def test_language_analysis_skips_oversized_files(tmp_path):
    path = tmp_path / "large.py"
    path.write_text("pass\n")
    result = language.analyze_project_languages(tmp_path, max_source_file_bytes=1)
    assert result.detected_languages == ["python"]
    assert result.analyzed_files == []
    assert result.diagnostics[0]["code"] == "source-size-limit"
