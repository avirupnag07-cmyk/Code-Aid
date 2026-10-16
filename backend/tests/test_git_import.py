from pathlib import Path

import pytest

from app.engine.git_import import (
    GitCommandResult,
    GitImportError,
    build_git_commands,
    import_repository,
    validate_repository_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/acme/project",
        "https://localhost/acme/project",
        "https://127.0.0.1/acme/project",
        "https://user:password@github.com/acme/project",
        "https://github.com/acme/project?token=secret",
    ],
)
def test_repository_url_requires_public_https_without_credentials(url):
    with pytest.raises(GitImportError):
        validate_repository_url(url)


def test_git_commands_are_argument_vectors_without_shell_interpolation(tmp_path: Path):
    commands = build_git_commands(
        "https://github.com/acme/project",
        "release/v1",
        tmp_path / "checkout",
    )
    assert all(isinstance(command, list) for command in commands)
    assert all(";" not in argument and "&&" not in argument for command in commands for argument in command)
    fetch = commands[2]
    assert "--no-recurse-submodules" in fetch
    assert "release/v1" in fetch


def test_mocked_repository_import_copies_subdirectory_and_persists_resolved_revision(tmp_path: Path):
    sha = "0123456789abcdef0123456789abcdef01234567"
    seen = []

    def runner(args, cwd, timeout):
        seen.append((list(args), cwd, timeout))
        if args[1:3] == ["init", "--quiet"]:
            checkout = Path(args[-1])
            (checkout / "src").mkdir(parents=True, exist_ok=True)
            (checkout / "src" / "app.py").write_text("raise RuntimeError('mock')")
            (checkout / "src" / "traceback.txt").write_text("RuntimeError: mock")
        if args[-2:] == ["rev-parse", "HEAD"]:
            return GitCommandResult(0, sha + "\n", "")
        return GitCommandResult(0, "", "")

    result = import_repository(
        "https://github.com/acme/project.git",
        "main",
        tmp_path / "project",
        subdirectory="src",
        command_runner=runner,
    )
    assert result.source_type == "git"
    assert result.root.joinpath("app.py").exists()
    assert result.root.joinpath("traceback.txt").read_text() == "RuntimeError: mock"
    assert result.repository == {
        "provider": "github",
        "url": "https://github.com/acme/project.git",
        "owner": "acme",
        "name": "project",
        "ref": "main",
        "sha": sha,
        "subdirectory": "src",
        "imported_at": result.repository["imported_at"],
    }
    assert not (result.root / ".git").exists()
    assert all(0 < timeout <= 60.0 for _, _, timeout in seen)


def test_git_failure_is_sanitized_and_cleans_checkout(tmp_path: Path):
    def failing_runner(args, cwd, timeout):
        if args[3] == "fetch":
            return GitCommandResult(128, "", "fatal: https://secret-token@example.invalid/private")
        return GitCommandResult(0, "", "")

    destination = tmp_path / "project"
    with pytest.raises(GitImportError, match="revision could not be fetched") as error:
        import_repository(
            "https://github.com/acme/project",
            "main",
            destination,
            command_runner=failing_runner,
        )
    assert "secret-token" not in str(error.value)
    assert not destination.exists()
    assert not list(tmp_path.glob(".git-import-*"))


def test_authenticated_git_runner_keeps_token_out_of_argv(monkeypatch, tmp_path: Path):
    from app.engine import git_import

    captured = {}

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(args, **kwargs):
        captured["args"] = list(args)
        captured["env"] = kwargs["env"]
        return Completed()

    monkeypatch.setattr(git_import.subprocess, "run", fake_run)
    git_import._default_command_runner(
        ["git", "-C", str(tmp_path), "fetch", "origin", "main"],
        tmp_path,
        1.0,
        auth_token="secret-token",
    )
    assert "secret-token" not in " ".join(captured["args"])
    assert captured["env"]["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    assert "secret-token" not in captured["env"]["GIT_CONFIG_VALUE_0"]
