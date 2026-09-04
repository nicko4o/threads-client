from __future__ import annotations

from pathlib import Path

import respx
from typer.testing import CliRunner

from threads_client.cli import app

runner = CliRunner()


@respx.mock
def test_cli_token_refresh(tmp_path: Path, base_url: str) -> None:
    respx.get(f"{base_url}/refresh_access_token").respond(
        200,
        json={"access_token": "NEW_REFRESHED_LONG_TOKEN", "token_type": "bearer", "expires_in": 5184000},
    )

    env_file = tmp_path / ".env"
    env_file.write_text("THREADS_ACCESS_TOKEN=OLD_EXPIRED_TOKEN\nOTHER_VAR=123\n", encoding="utf-8")

    result = runner.invoke(app, ["token", "refresh", "--env-file", str(env_file)])
    assert result.exit_code == 0
    assert "Token refreshed successfully" in result.stdout

    updated_content = env_file.read_text(encoding="utf-8")
    assert "THREADS_ACCESS_TOKEN=NEW_REFRESHED_LONG_TOKEN" in updated_content
    assert "OTHER_VAR=123" in updated_content


@respx.mock
def test_cli_token_exchange(tmp_path: Path, base_url: str) -> None:
    respx.get(f"{base_url}/access_token").respond(
        200,
        json={"access_token": "NEW_EXCHANGED_TOKEN", "token_type": "bearer", "expires_in": 5184000},
    )

    env_file = tmp_path / ".env"
    env_file.write_text("SOME_VAR=hello\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "token",
            "exchange",
            "--short-token",
            "SHORT_123",
            "--app-secret",
            "SECRET_456",
            "--env-file",
            str(env_file),
        ],
    )
    assert result.exit_code == 0
    assert "Token exchanged successfully" in result.stdout

    updated_content = env_file.read_text(encoding="utf-8")
    assert "THREADS_ACCESS_TOKEN=NEW_EXCHANGED_TOKEN" in updated_content
    # File permissions should be restricted (0o600)
    assert (env_file.stat().st_mode & 0o777) == 0o600


@respx.mock
def test_cli_handles_threads_api_error_gracefully(tmp_path: Path, base_url: str) -> None:
    respx.get(f"{base_url}/access_token").respond(
        400,
        json={"error": {"message": "Invalid OAuth secret", "code": 190}},
    )
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "token",
            "exchange",
            "--short-token",
            "BAD_TOKEN",
            "--app-secret",
            "BAD_SECRET",
            "--env-file",
            str(env_file),
        ],
    )
    assert result.exit_code == 1
    assert "Error: Invalid OAuth secret" in result.stdout
    assert "Traceback" not in result.stdout
