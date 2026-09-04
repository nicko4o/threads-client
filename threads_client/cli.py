from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Annotated

import typer

from threads_client.client import ThreadsClient

app = typer.Typer(help="Meta Threads API Client CLI")
token_app = typer.Typer(help="Token exchange and renewal commands")
app.add_typer(token_app, name="token")


def _update_env_var(env_path: Path, key: str, value: str) -> None:
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)

    replaced = False
    prefix = f"{key}="
    for i, line in enumerate(lines):
        if line.strip().startswith(prefix):
            lines[i] = f"{key}={value}\n"
            replaced = True
            break

    if not replaced:
        lines.append(f"{key}={value}\n")

    env_path.write_text("".join(lines), encoding="utf-8")


def _read_env_var(env_path: Path, key: str) -> str | None:
    if not env_path.exists():
        return None
    prefix = f"{key}="
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(prefix):
            return line.strip()[len(prefix) :].strip("\"'")
    return None


@token_app.command("refresh")
def refresh_token_cmd(
    env_file: Annotated[Path, typer.Option(help="Path to .env file")] = Path(".env"),
    token: Annotated[str | None, typer.Option(help="Access token to refresh")] = None,
) -> None:
    """Refresh an existing long-lived token (extends 60 days)."""
    current_token = token or os.getenv("THREADS_ACCESS_TOKEN") or _read_env_var(env_file, "THREADS_ACCESS_TOKEN")
    if not current_token:
        typer.secho("Error: No access token provided or found in environment/.env", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    async def _run() -> None:
        async with ThreadsClient(user_id="me", access_token=current_token) as client:
            info = await client.tokens.refresh(current_token)
            _update_env_var(env_file, "THREADS_ACCESS_TOKEN", info.access_token)
            typer.secho(
                f"Token refreshed successfully! Expires in: {info.expires_in}s. Written to {env_file}",
                fg=typer.colors.GREEN,
            )

    asyncio.run(_run())


@token_app.command("exchange")
def exchange_token_cmd(
    short_token: Annotated[str, typer.Option(help="Short-lived user access token")],
    app_secret: Annotated[str, typer.Option(help="Meta App Secret")],
    env_file: Annotated[Path, typer.Option(help="Path to .env file")] = Path(".env"),
) -> None:
    """Exchange short-lived OAuth token for 60-day long-lived token."""

    async def _run() -> None:
        async with ThreadsClient(user_id="me", access_token="temp") as client:
            info = await client.tokens.exchange(short_token=short_token, app_secret=app_secret)
            _update_env_var(env_file, "THREADS_ACCESS_TOKEN", info.access_token)
            typer.secho(
                f"Token exchanged successfully! Expires in: {info.expires_in}s. Written to {env_file}",
                fg=typer.colors.GREEN,
            )

    asyncio.run(_run())


if __name__ == "__main__":
    app()
