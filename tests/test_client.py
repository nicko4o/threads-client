from __future__ import annotations

import httpx
import pytest
import pytest_mock
import respx

from threads_client import ThreadsClient
from threads_client.models import CarouselMediaItem


@respx.mock
async def test_client_convenience_post_methods(
    base_url: str, user_id: str, access_token: str, mocker: pytest_mock.MockerFixture
) -> None:
    mocker.patch("asyncio.sleep")
    respx.post(f"{base_url}/{user_id}/threads").respond(200, json={"id": "cnt_conv_1"})
    respx.get(f"{base_url}/cnt_conv_1").respond(200, json={"status": "FINISHED"})
    respx.post(f"{base_url}/{user_id}/threads_publish").respond(200, json={"id": "post_conv_100"})

    client = ThreadsClient(user_id=user_id, access_token=access_token)
    try:
        # Test backward-compatible convenience method .post()
        post_id = await client.post("Convenience post", topic_tag="Baseball")
        assert post_id == "post_conv_100"
    finally:
        await client.close()


@respx.mock
async def test_client_convenience_carousel_method(
    base_url: str, user_id: str, access_token: str, mocker: pytest_mock.MockerFixture
) -> None:
    mocker.patch("asyncio.sleep")
    respx.post(f"{base_url}/{user_id}/threads").side_effect = [
        httpx.Response(200, json={"id": "cnt_conv_item_1"}),
        httpx.Response(200, json={"id": "cnt_conv_parent"}),
    ]
    respx.get(f"{base_url}/cnt_conv_item_1").respond(200, json={"status": "FINISHED"})
    respx.get(f"{base_url}/cnt_conv_parent").respond(200, json={"status": "FINISHED"})
    respx.post(f"{base_url}/{user_id}/threads_publish").respond(200, json={"id": "post_conv_carousel_200"})

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        items = [CarouselMediaItem(media_type="IMAGE", url="https://example.com/single.jpg")]
        post_id = await client.post_carousel("Carousel convenience", items=items)
        assert post_id == "post_conv_carousel_200"


@respx.mock
async def test_client_without_token_raises_authentication_error() -> None:
    from threads_client.exceptions import ThreadsAuthenticationError

    async with ThreadsClient() as client:
        with pytest.raises(ThreadsAuthenticationError, match=r"Access token is required"):
            await client.posts.create(text="No token test")


@respx.mock
async def test_client_without_token_allows_tokens_exchange(base_url: str) -> None:
    respx.get(f"{base_url}/access_token").respond(
        200,
        json={"access_token": "NEW_TOKEN", "token_type": "bearer", "expires_in": 5184000},
    )
    async with ThreadsClient() as client:
        info = await client.tokens.exchange(short_token="SHORT", app_secret="SECRET")
        assert info.access_token == "NEW_TOKEN"


@respx.mock
async def test_client_token_dynamic_mutation_ssot(base_url: str) -> None:
    respx.post(f"{base_url}/me/threads").respond(200, json={"id": "cnt_dynamic_1"})
    respx.get(f"{base_url}/cnt_dynamic_1").respond(200, json={"status": "FINISHED"})
    respx.post(f"{base_url}/me/threads_publish").respond(200, json={"id": "post_dynamic_100"})

    async with ThreadsClient() as client:
        assert client.access_token is None
        # Dynamically set access_token on client
        client.access_token = "DYNAMIC_TOKEN_123"
        assert client.posts._require_access_token() == "DYNAMIC_TOKEN_123"

        # Dynamically change user_id
        client.user_id = "me"
        assert client.posts._user_id == "me"

        result = await client.posts.create(text="Dynamic token test")
        assert result.post_id == "post_dynamic_100"
