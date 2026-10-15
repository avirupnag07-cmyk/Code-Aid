import io
import zipfile


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
    }


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
    report = client.get("/api/investigations/" + record["id"] + "/report")
    assert report.status_code == 200
    assert "## Ranked hypotheses" in report.text


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
