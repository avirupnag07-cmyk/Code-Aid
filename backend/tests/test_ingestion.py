import io
import zipfile
from pathlib import Path

import pytest

from app.engine.ingestion import (
    ArchiveLimitError,
    IngestionError,
    IngestionLimits,
    UnsafeArchiveError,
    ingest_zip,
)


def make_zip(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return stream.getvalue()


def test_zip_ingestion_copies_source_without_executing_it(tmp_path: Path):
    destination = tmp_path / "project"
    result = ingest_zip(
        make_zip(
            [
                ("app.py", "raise RuntimeError('must not execute')"),
                ("traceback.txt", "RuntimeError: must not execute"),
            ]
        ),
        destination,
    )
    assert result.source_type == "upload"
    assert result.files == ["app.py", "traceback.txt"]
    assert destination.joinpath("app.py").read_text() == "raise RuntimeError('must not execute')"


@pytest.mark.parametrize("member", ["../escape.py", "/absolute.py", "C:/drive.py", "folder/../../escape.py"])
def test_zip_path_traversal_and_absolute_names_are_rejected(tmp_path: Path, member: str):
    with pytest.raises(UnsafeArchiveError):
        ingest_zip(make_zip([(member, "x")]), tmp_path / "project")


def test_malformed_zip_is_rejected_and_destination_is_cleaned(tmp_path: Path):
    destination = tmp_path / "project"
    with pytest.raises(IngestionError, match="valid ZIP"):
        ingest_zip(b"not-a-zip", destination)
    assert not destination.exists()


def test_archive_member_and_total_limits_are_enforced(tmp_path: Path):
    data = make_zip([("a.py", "12345"), ("b.py", "67890")])
    limits = IngestionLimits(max_member_bytes=4, max_uncompressed_bytes=20)
    with pytest.raises(ArchiveLimitError):
        ingest_zip(data, tmp_path / "project", limits=limits)


def test_sample_catalog_rejects_unknown_or_traversing_ids(settings):
    from app.engine.ingestion import IngestionError, SampleCatalog

    catalog = SampleCatalog(settings.samples_dir)
    with pytest.raises(IngestionError):
        catalog.describe("../samples")
    with pytest.raises(IngestionError):
        catalog.describe("does-not-exist")
