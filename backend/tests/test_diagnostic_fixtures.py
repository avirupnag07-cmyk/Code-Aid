"""Registry and native-diagnostic coverage for deterministic broken projects."""

import json
from pathlib import Path
import zipfile

import pytest

from app.engine.language_analysis import AdapterRegistry


FIXTURES = Path(__file__).parent / "fixtures"
CASES = (
    ("python", "broken.py"),
    ("javascript", "broken.js"),
    ("typescript", "broken.ts"),
    ("java", "Broken.java"),
    ("c", "broken.c"),
    ("cpp", "broken.cpp"),
    ("go", "broken.go"),
    ("rust", "broken.rs"),
)


def _fixture(language_id: str):
    root = FIXTURES / language_id
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    return root, metadata


@pytest.mark.parametrize("language_id, filename", CASES)
def test_every_fixture_uses_the_registry_and_reports_tool_state(language_id, filename):
    root, metadata = _fixture(language_id)
    registry = AdapterRegistry()
    adapter = registry.get(language_id)
    assert adapter is not None
    detected = registry.detect(root)
    assert [path.name for path in detected[language_id]] == [filename]

    result = registry.analyze(root)
    assert result.detected_languages == [language_id]
    assert result.toolchains[language_id]["id"] == language_id
    assert result.toolchains[language_id]["tool"] == adapter.toolchain.command

    expected = metadata["expected_diagnostic"]
    if result.toolchains[language_id]["available"]:
        assert filename in result.analyzed_files
    else:
        blocked = [item for item in result.diagnostics if item["code"] == "tool-unavailable"]
        assert blocked, "unavailable {} must be reported as blocked".format(language_id)
        assert blocked[0]["path"] == expected["path"]
        assert blocked[0]["severity"] == "info"


@pytest.mark.parametrize("language_id, filename", CASES)
def test_available_fixture_toolchains_emit_normalized_locations(language_id, filename):
    root, metadata = _fixture(language_id)
    result = AdapterRegistry().analyze(root)
    toolchain = result.toolchains[language_id]
    if not toolchain["available"]:
        pytest.skip("BLOCKED: {} ({})".format(toolchain["tool"], toolchain["reason"]))

    diagnostics = [item for item in result.diagnostics if item["code"] != "tool-unavailable"]
    assert diagnostics, "{} native check produced no diagnostic".format(language_id)
    expected = metadata["expected_diagnostic"]
    matching = [
        item
        for item in diagnostics
        if item["path"] == expected["path"]
        and item["line"] == expected["line"]
        and item["severity"] == expected["severity"]
    ]
    assert matching, diagnostics
    assert all(item["language"] == language_id for item in diagnostics)
    assert all(item["source"] == "adapter" for item in diagnostics)


def test_relative_fixture_root_still_invokes_native_check_from_the_fixture_directory():
    result = AdapterRegistry().analyze(Path("backend/tests/fixtures/javascript"))
    assert result.detected_languages == ["javascript"]
    assert result.analyzed_files == ["broken.js"]
    diagnostic = next(item for item in result.diagnostics if item["code"] != "tool-unavailable")
    assert diagnostic["path"] == "broken.js"
    assert diagnostic["line"] == 1


@pytest.mark.parametrize("language_id, filename", CASES)
def test_fixture_zip_upload_runs_diagnostics_without_importing_project_code(client, language_id, filename):
    root, _ = _fixture(language_id)
    import io

    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        for path in sorted(root.iterdir()):
            archive.write(path, path.name)
    response = client.post(
        "/api/investigations",
        files={"archive": ("fixture.zip", payload.getvalue(), "application/zip")},
    )
    assert response.status_code == 201
    record = response.json()
    assert record["source"]["detected_languages"] == [language_id]
    assert record["results"]["language_analysis"]["detected_languages"] == [language_id]
    assert record["results"]["language_diagnostics"]
