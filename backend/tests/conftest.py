from pathlib import Path

import pytest

from app.config import Settings
from app.main import create_app


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=ROOT,
        database_path=tmp_path / "code-aid.sqlite3",
        storage_dir=tmp_path / "investigations",
        samples_dir=ROOT / "samples",
        allowed_origins=("*",),
    )


@pytest.fixture()
def client(settings: Settings):
    from fastapi.testclient import TestClient

    return TestClient(create_app(settings))
