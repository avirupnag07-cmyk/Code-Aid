import io
import zipfile
from pathlib import Path

from app.engine.ingestion import IngestedProject


def test_health_and_sample_catalog_are_available(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    samples = client.get("/api/samples")
    assert samples.status_code == 200
    assert {item["id"] for item in samples.json()} >= {
        "simple-reproducible-bug",
        "unexpected-type-bug",
        "regression-after-fix-bug",
        "javascript-syntax",
        "typescript-syntax",
        "java-syntax",
        "c-syntax",
        "cpp-syntax",
        "go-syntax",
        "rust-syntax",
    }


def test_language_adapter_sample_keeps_python_test_generation_disabled(client):
    created = client.post(
        "/api/investigations",
        json={"sample_id": "javascript-syntax", "title": "JavaScript syntax investigation"},
    )
    assert created.status_code == 201
    record = created.json()
    assert record["source"]["detected_languages"] == ["javascript"]
    assert record["results"]["generated_tests"] == []
    assert record["results"]["language_analysis"]["diagnostics"]
    assert record["results"]["facts"][-1]["text"].startswith("No language-native test generator")


def test_language_support_matrix_reports_all_adapters_and_tool_state(client):
    response = client.get("/api/languages")
    assert response.status_code == 200
    matrix = response.json()
    assert {item["id"] for item in matrix} >= {
        "python",
        "javascript",
        "typescript",
        "java",
        "c",
        "cpp",
        "go",
        "rust",
    }
    assert all("available" in item and "reason" in item for item in matrix)


def test_json_creation_persists_results_and_report(client):
    created = client.post(
        "/api/investigations",
        json={"sample_id": "simple-reproducible-bug", "title": "API tax investigation"},
    )
    assert created.status_code == 201
    record = created.json()
    assert record["status"] == "analyzed"
    assert record["results"]["findings"]
    assert record["results"]["generated_tests"][0]["validation_status"] == "valid"
    fetched = client.get("/api/investigations/" + record["id"])
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "API tax investigation"
    listed = client.get("/api/investigations")
    summary = next(item for item in listed.json() if item["id"] == record["id"])
    assert summary["finding_count"] == len(record["results"]["findings"])
    assert summary["hypothesis_count"] == len(record["results"]["hypotheses"])
    report = client.get("/api/investigations/" + record["id"] + "/report")
    assert report.status_code == 200
    assert "## Ranked hypotheses" in report.text
    assert "## Language analysis" in report.text


def test_investigation_records_detected_languages_and_adapter_diagnostics(client):
    created = client.post("/api/investigations", json={"sample_id": "simple-reproducible-bug"})
    assert created.status_code == 201
    record = created.json()
    assert record["source"]["language"] == "python"
    assert record["source"]["detected_languages"] == ["python"]
    assert record["results"]["language"] == "python"
    assert record["results"]["detected_languages"] == ["python"]
    assert record["results"]["language_analysis"]["detected_languages"] == ["python"]
    assert isinstance(record["results"]["language_diagnostics"], list)


def test_invalid_creation_and_uploads_return_clear_validation_errors(client):
    missing_source = client.post("/api/investigations", json={"title": "No source"})
    assert missing_source.status_code == 422
    bad_upload = client.post(
        "/api/investigations",
        files={"archive": ("project.txt", b"not a zip", "text/plain")},
    )
    assert bad_upload.status_code == 400
    traversal = io.BytesIO()
    with zipfile.ZipFile(traversal, "w") as archive:
        archive.writestr("../../escape.py", "pass")
    unsafe_upload = client.post(
        "/api/investigations",
        files={"archive": ("project.zip", traversal.getvalue(), "application/zip")},
    )
    assert unsafe_upload.status_code == 400
    assert "traversal" in unsafe_upload.json()["detail"]


def test_multipart_sample_creation_accepts_form_fields(client):
    created = client.post(
        "/api/investigations",
        data={"sample_id": "unexpected-type-bug", "title": "Unexpected profile value"},
    )
    assert created.status_code == 201
    assert created.json()["source"]["sample_id"] == "unexpected-type-bug"


def test_repository_creation_uses_importer_and_persists_token_free_revision_metadata(client, monkeypatch, tmp_path: Path):
    def fake_import(url, ref, destination, **kwargs):
        destination.mkdir(parents=True)
        (destination / "app.py").write_text("raise RuntimeError('mock repository')")
        (destination / "traceback.txt").write_text("RuntimeError: mock repository")
        return IngestedProject(
            root=destination,
            source_type="git",
            traceback="RuntimeError: mock repository",
            files=["app.py", "traceback.txt"],
            metadata={},
            repository={
                "provider": "github",
                "url": url,
                "owner": "acme",
                "name": "project",
                "ref": ref,
                "sha": "0123456789abcdef0123456789abcdef01234567",
                "subdirectory": None,
                "imported_at": "2026-01-01T00:00:00+00:00",
            },
        )

    monkeypatch.setattr("app.api.routes.import_repository", fake_import)
    created = client.post(
        "/api/investigations",
        json={
            "repository": {"url": "https://github.com/acme/project.git", "ref": "main"},
            "title": "Mock repository investigation",
        },
    )
    assert created.status_code == 201
    source = created.json()["source"]
    assert source["source_type"] == "git"
    assert source["repository"]["sha"] == "0123456789abcdef0123456789abcdef01234567"
    assert "repository" not in source["metadata"]
    assert "token" not in source["metadata"]


def test_patch_verification_is_non_mutating_and_rejects_escape(client):
    created = client.post("/api/investigations", json={"sample_id": "simple-reproducible-bug"})
    assert created.status_code == 201
    record = created.json()
    result = client.post(
        "/api/investigations/{}/verify".format(record["id"]),
        json={"file_path": "calculator.py", "content": "def add_tax(amount, tax_rate):\n    return amount + float(tax_rate)\n"},
    )
    assert result.status_code == 200
    assert result.json()["verification"]["safe_to_apply"] is True
    assert result.json()["verification"]["status"] == "execution-unavailable"
    assert result.json()["verification"]["baseline_execution"]["status"] == "unavailable"
    assert result.json()["verification"]["patched_execution"]["status"] == "unavailable"
    unsafe = client.post(
        "/api/investigations/{}/verify".format(record["id"]),
        json={"file_path": "../secret.py", "content": "pass"},
    )
    assert unsafe.status_code == 400


def test_delete_removes_persisted_investigation(client):
    created = client.post("/api/investigations", json={"sample_id": "regression-after-fix-bug"})
    identifier = created.json()["id"]
    deleted = client.delete("/api/investigations/" + identifier)
    assert deleted.status_code == 200
    assert client.get("/api/investigations/" + identifier).status_code == 404
