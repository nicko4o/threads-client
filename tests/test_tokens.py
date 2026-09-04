from __future__ import annotations

import pytest
import respx

from threads_client import ThreadsClient
from threads_client.exceptions import ThreadsAPIError


@respx.mock
async def test_token_exchange_success(base_url: str) -> None:
    respx.get(f"{base_url}/access_token").respond(
        200,
        json={"access_token": "TH_LONG_LIVED_TOKEN_123", "token_type": "bearer", "expires_in": 5184000},
    )

    async with ThreadsClient(user_id="123", access_token="temp") as client:
        info = await client.tokens.exchange(short_token="TH_SHORT_TOKEN", app_secret="MY_APP_SECRET")
        assert info.access_token == "TH_LONG_LIVED_TOKEN_123"
        assert info.token_type == "bearer"
        assert info.expires_in == 5184000


@respx.mock
async def test_token_exchange_failure(base_url: str) -> None:
    respx.get(f"{base_url}/access_token").respond(
        400,
        json={"error": {"message": "Invalid OAuth access token", "code": 190}},
    )

    async with ThreadsClient(user_id="123", access_token="temp") as client:
        with pytest.raises(ThreadsAPIError) as exc_info:
            await client.tokens.exchange(short_token="INVALID", app_secret="SECRET")
        assert exc_info.value.code == 190


@respx.mock
async def test_token_refresh_success(base_url: str) -> None:
    respx.get(f"{base_url}/refresh_access_token").respond(
        200,
        json={"access_token": "TH_REFRESHED_TOKEN_999", "token_type": "bearer", "expires_in": 5184000},
    )

    async with ThreadsClient(user_id="123", access_token="OLD_TOKEN") as client:
        info = await client.tokens.refresh(long_token="OLD_TOKEN")
        assert info.access_token == "TH_REFRESHED_TOKEN_999"
        assert info.expires_in == 5184000


@respx.mock
async def test_token_exchange_logging_masks_secret(base_url: str, caplog: pytest.LogCaptureFixture) -> None:
    import logging

    respx.get(f"{base_url}/access_token").respond(
        400,
        json={"error": {"message": "Invalid OAuth secret", "code": 190}},
    )

    async with ThreadsClient() as client:
        with caplog.at_level(logging.ERROR), pytest.raises(ThreadsAPIError):
            await client.tokens.exchange(short_token="SUPER_SHORT_SECRET_TOKEN", app_secret="SUPER_APP_SECRET")

    assert "SUPER_SHORT_SECRET_TOKEN" not in caplog.text
    assert "SUPER_APP_SECRET" not in caplog.text
