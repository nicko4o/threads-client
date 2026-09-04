from __future__ import annotations

import httpx
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
