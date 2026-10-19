import os
from pathlib import Path

import pytest

from app import config
from app.config import Settings


LOCAL_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def clean_config_environment(monkeypatch):
    for name in os.environ:
        if name.startswith("CODE_AID_"):
            monkeypatch.delenv(name)


def test_default_root_is_repository_not_backend(tmp_path, monkeypatch):
    # Isolate the developer's private .env while testing actual module location.
    monkeypatch.setattr(config, "_read_dotenv", lambda _path: {})
    monkeypatch.chdir(tmp_path)
    settings = Settings.from_env()
    assert settings.project_root == ROOT
    assert settings.database_path == ROOT / "backend/data/code_aid.sqlite3"
    assert settings.storage_dir == ROOT / "backend/data/investigations"
    assert settings.samples_dir == ROOT / "samples"
    assert settings.samples_dir.is_dir()
    assert settings.allowed_origins == LOCAL_ORIGINS


def test_default_loader_reads_only_repository_dotenv(tmp_path, monkeypatch):
    paths = []

    def read_dotenv(path):
        paths.append(path)
        return {}

    monkeypatch.setattr(config, "_read_dotenv", read_dotenv)
    monkeypatch.chdir(tmp_path)
    Settings.from_env()
    assert paths == [ROOT / ".env"]


def test_explicit_root_defaults_ignore_working_directory_dotenv(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    root.mkdir()
    (tmp_path / ".env").write_text("CODE_AID_STORAGE=wrong\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    settings = Settings.from_env(Path("checkout"))
    assert settings.project_root == root
    assert settings.database_path == root / "backend/data/code_aid.sqlite3"
    assert settings.storage_dir == root / "backend/data/investigations"
    assert settings.samples_dir == root / "samples"
    assert settings.allowed_origins == LOCAL_ORIGINS


def test_dotenv_comments_quotes_and_repo_relative_paths(tmp_path):
    (tmp_path / ".env").write_text(
        "\ufeff# Local overrides\n"
        "CODE_AID_DATABASE = 'private data/local.sqlite3' # database\n"
        'export CODE_AID_STORAGE="private data/#investigations" # storage\n'
        "CODE_AID_SAMPLES=fixtures/samples # sample catalog\n"
        "CODE_AID_RUN_TIMEOUT_SECONDS=9 # seconds\n"
        'CODE_AID_ALLOWED_ORIGINS="http://localhost:5173, http://127.0.0.1:5173"\n'
        "CODE_AID_DOCKER_IMAGE=runner:local#tag\n",
        encoding="utf-8",
    )
    settings = Settings.from_env(tmp_path)
    assert settings.database_path == tmp_path / "private data/local.sqlite3"
    assert settings.storage_dir == tmp_path / "private data/#investigations"
    assert settings.samples_dir == tmp_path / "fixtures/samples"
    assert settings.run_timeout_seconds == 9
    assert settings.allowed_origins == LOCAL_ORIGINS
    assert settings.docker_image == "runner:local#tag"


def test_process_environment_wins_over_dotenv_including_empty_values(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "CODE_AID_DATABASE=file.sqlite3\n"
        "CODE_AID_STORAGE=file-storage\n"
        "CODE_AID_SAMPLES=file-samples\n"
        "CODE_AID_RUN_TIMEOUT_SECONDS=99\n"
        "CODE_AID_DOCKER_IMAGE=file-image\n"
        "CODE_AID_ALLOWED_ORIGINS=https://file.example\n",
        encoding="utf-8",
    )
    absolute_database = tmp_path / "absolute.sqlite3"
    monkeypatch.setenv("CODE_AID_DATABASE", str(absolute_database))
    monkeypatch.setenv("CODE_AID_STORAGE", "process-storage")
    monkeypatch.setenv("CODE_AID_SAMPLES", "")
    monkeypatch.setenv("CODE_AID_RUN_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("CODE_AID_DOCKER_IMAGE", "process-image")
    monkeypatch.setenv("CODE_AID_ALLOWED_ORIGINS", "https://process.example")
    settings = Settings.from_env(tmp_path)
    assert settings.database_path == absolute_database
    assert settings.storage_dir == tmp_path / "process-storage"
    assert settings.samples_dir == tmp_path / "samples"
    assert settings.run_timeout_seconds == 7
    assert settings.docker_image == "process-image"
    assert settings.allowed_origins == ("https://process.example",)


def test_dotenv_is_private_literal_data_and_does_not_mutate_environment(tmp_path, monkeypatch):
    private_file = tmp_path / ".env"
    marker = tmp_path / "shell-must-not-run"
    monkeypatch.setenv("CONFIG_TEST_EXISTING", "process-value")
    private_file.write_text(
        "CONFIG_TEST_PRIVATE=private-value\n"
        "CONFIG_TEST_EXISTING=file-value\n"
        f'CODE_AID_DOCKER_IMAGE="$(touch {marker}); `touch {marker}`; $CONFIG_TEST_EXISTING"\n'
        "CODE_AID_STORAGE='${CONFIG_TEST_PRIVATE}/literal\\path'\n",
        encoding="utf-8",
    )
    private_file.chmod(0o600)
    original = private_file.read_bytes()
    original_mode = private_file.stat().st_mode
    environment = dict(os.environ)
    settings = Settings.from_env(tmp_path)
    assert settings.docker_image == f"$(touch {marker}); `touch {marker}`; $CONFIG_TEST_EXISTING"
    assert settings.storage_dir == tmp_path / "${CONFIG_TEST_PRIVATE}/literal\\path"
    assert not marker.exists()
    assert dict(os.environ) == environment
    assert private_file.read_bytes() == original
    assert private_file.stat().st_mode == original_mode
    # Values belong to one Settings load, not future calls or subprocesses.
    private_file.unlink()
    assert Settings.from_env(tmp_path).docker_image == "code-aid-runner:0.1.0"


@pytest.mark.parametrize("value", ["", " , ", "# local defaults"])
def test_empty_origins_use_local_defaults(tmp_path, value):
    (tmp_path / ".env").write_text(f"CODE_AID_ALLOWED_ORIGINS={value}\n", encoding="utf-8")
    assert Settings.from_env(tmp_path).allowed_origins == LOCAL_ORIGINS


@pytest.mark.parametrize("value", ["invalid", "0", "-1", ""])
def test_invalid_integer_overrides_keep_safe_defaults(tmp_path, value):
    (tmp_path / ".env").write_text(f"CODE_AID_RUN_TIMEOUT_SECONDS={value}\n", encoding="utf-8")
    assert Settings.from_env(tmp_path).run_timeout_seconds == 20


def test_malformed_assignments_are_ignored(tmp_path):
    (tmp_path / ".env").write_text(
        "source other.env\n"
        "CODE_AID_DOCKER_IMAGE='unclosed\n"
        'CODE_AID_STORAGE="closed" trailing-junk\n'
        "CODE_AID_RUN_TIMEOUT_SECONDS\n"
        "not-a-key=value\n",
        encoding="utf-8",
    )
    settings = Settings.from_env(tmp_path)
    assert settings.docker_image == "code-aid-runner:0.1.0"
    assert settings.storage_dir == tmp_path / "backend/data/investigations"
    assert settings.run_timeout_seconds == 20
