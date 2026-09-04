from __future__ import annotations

import logging

import httpx
import pytest
import pytest_mock
import respx

from threads_client import ThreadsClient
from threads_client.exceptions import (
    ThreadsAPIError,
    ThreadsMediaProcessingError,
    ThreadsTimeoutError,
    ThreadsValidationError,
)
from threads_client.models import CarouselMediaItem, ThreadsPaging


def _req_body(call_index: int = 0) -> str:
    body = respx.calls[call_index].request.content
    if isinstance(body, bytes):
        return body.decode("utf-8")
    return str(body or "")


@respx.mock
async def test_create_text_post(
    base_url: str, user_id: str, access_token: str, mocker: pytest_mock.MockerFixture
) -> None:
    mocker.patch("asyncio.sleep")
    respx.post(f"{base_url}/{user_id}/threads").respond(200, json={"id": "cnt_text_1"})
    respx.get(f"{base_url}/cnt_text_1").respond(200, json={"status": "FINISHED"})
    respx.post(f"{base_url}/{user_id}/threads_publish").respond(200, json={"id": "post_text_100"})

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        result = await client.posts.create(text="Hello Threads!")
        assert result.post_id == "post_text_100"
        assert result.container_id == "cnt_text_1"

    body = _req_body(0)
    assert "media_type=TEXT" in body
    assert "text=Hello+Threads%21" in body or "text=Hello Threads!" in body.replace("+", " ")
    assert f"access_token={access_token}" in body


@respx.mock
async def test_create_image_post(
    base_url: str, user_id: str, access_token: str, mocker: pytest_mock.MockerFixture
) -> None:
    mocker.patch("asyncio.sleep")
    respx.post(f"{base_url}/{user_id}/threads").respond(200, json={"id": "cnt_img_1"})
    respx.get(f"{base_url}/cnt_img_1").respond(200, json={"status": "FINISHED"})
    respx.post(f"{base_url}/{user_id}/threads_publish").respond(200, json={"id": "post_img_200"})

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        result = await client.posts.create(
            text="Baseball photo",
            image_url="https://example.com/photo.jpg",
            topic_tag="MLB",
        )
        assert result.post_id == "post_img_200"

    body = _req_body(0)
    assert "media_type=IMAGE" in body
    assert "image_url=https%3A%2F%2Fexample.com%2Fphoto.jpg" in body or "image_url=https://example.com/photo.jpg" in (
        body
    )
    assert "topic_tag=MLB" in body


@respx.mock
async def test_create_video_post(
    base_url: str, user_id: str, access_token: str, mocker: pytest_mock.MockerFixture
) -> None:
    mocker.patch("asyncio.sleep")
    respx.post(f"{base_url}/{user_id}/threads").respond(200, json={"id": "cnt_vid_1"})
    respx.get(f"{base_url}/cnt_vid_1").respond(200, json={"status": "FINISHED"})
    respx.post(f"{base_url}/{user_id}/threads_publish").respond(200, json={"id": "post_vid_300"})

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        result = await client.posts.create(
            text="Highlight clip",
            video_url="https://example.com/video.mp4",
        )
        assert result.post_id == "post_vid_300"

    body = _req_body(0)
    assert "media_type=VIDEO" in body
    assert "video_url=https%3A%2F%2Fexample.com%2Fvideo.mp4" in body or "video_url=https://example.com/video.mp4" in (
        body
    )


@respx.mock
async def test_create_carousel_post(
    base_url: str, user_id: str, access_token: str, mocker: pytest_mock.MockerFixture
) -> None:
    mocker.patch("asyncio.sleep")
    respx.post(f"{base_url}/{user_id}/threads").side_effect = [
        httpx.Response(200, json={"id": "cnt_item_1"}),
        httpx.Response(200, json={"id": "cnt_item_2"}),
        httpx.Response(200, json={"id": "cnt_carousel_parent"}),
    ]
    respx.get(f"{base_url}/cnt_item_1").respond(200, json={"status": "FINISHED"})
    respx.get(f"{base_url}/cnt_item_2").respond(200, json={"status": "FINISHED"})
    respx.get(f"{base_url}/cnt_carousel_parent").respond(200, json={"status": "FINISHED"})
    respx.post(f"{base_url}/{user_id}/threads_publish").respond(200, json={"id": "post_carousel_400"})

    items = [
        CarouselMediaItem(media_type="IMAGE", url="https://example.com/item1.png"),
        CarouselMediaItem(media_type="VIDEO", url="https://example.com/item2.mp4"),
    ]

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        result = await client.posts.create_carousel(
            text="Double highlight",
            items=items,
            topic_tag="Baseball",
        )
        assert result.post_id == "post_carousel_400"
        assert result.container_id == "cnt_carousel_parent"


async def test_create_carousel_validation(user_id: str, access_token: str) -> None:
    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        with pytest.raises(ThreadsValidationError, match="Carousel items cannot be empty"):
            await client.posts.create_carousel(text="Empty", items=[])


@respx.mock
async def test_polling_error_raises_media_processing_error(
    base_url: str, user_id: str, access_token: str, mocker: pytest_mock.MockerFixture
) -> None:
    mocker.patch("asyncio.sleep")
    respx.post(f"{base_url}/{user_id}/threads").respond(200, json={"id": "cnt_fail"})
    respx.get(f"{base_url}/cnt_fail").respond(
        200, json={"status": "ERROR", "error_message": "Media format unsupported"}
    )

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        with pytest.raises(ThreadsMediaProcessingError, match="Media format unsupported"):
            await client.posts.create(text="Fail test", image_url="https://example.com/bad.png")


@respx.mock
async def test_polling_timeout_raises_threads_timeout(
    base_url: str, user_id: str, access_token: str, mocker: pytest_mock.MockerFixture
) -> None:
    mocker.patch("asyncio.sleep")
    respx.post(f"{base_url}/{user_id}/threads").respond(200, json={"id": "cnt_slow"})
    respx.get(f"{base_url}/cnt_slow").respond(200, json={"status": "IN_PROGRESS"})

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        with pytest.raises(ThreadsTimeoutError, match=r"did not finish processing"):
            await client.posts.create(text="Timeout test", image_url="https://example.com/slow.png")


@respx.mock
async def test_publish_retry_on_media_not_ready_4279009(
    base_url: str, user_id: str, access_token: str, mocker: pytest_mock.MockerFixture
) -> None:
    mock_sleep = mocker.patch("asyncio.sleep")
    respx.post(f"{base_url}/{user_id}/threads").respond(200, json={"id": "cnt_retry_media"})
    respx.get(f"{base_url}/cnt_retry_media").respond(200, json={"status": "FINISHED"})

    route_publish = respx.post(f"{base_url}/{user_id}/threads_publish")
    route_publish.side_effect = [
        httpx.Response(
            400,
            json={
                "error": {
                    "message": "The requested resource does not exist",
                    "code": 24,
                    "error_subcode": 4279009,
                }
            },
        ),
        httpx.Response(200, json={"id": "post_retry_media_ok"}),
    ]

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        result = await client.posts.create(text="Media retry", image_url="https://example.com/img.png")
        assert result.post_id == "post_retry_media_ok"

    assert mock_sleep.call_count >= 1


@respx.mock
async def test_transient_500_retry_success(
    base_url: str, user_id: str, access_token: str, mocker: pytest_mock.MockerFixture
) -> None:
    mock_sleep = mocker.patch("asyncio.sleep")
    route_create = respx.post(f"{base_url}/{user_id}/threads")
    route_create.side_effect = [
        httpx.Response(500, json={"error": {"message": "Internal Server Error"}}),
        httpx.Response(200, json={"id": "cnt_transient_ok"}),
    ]
    respx.get(f"{base_url}/cnt_transient_ok").respond(200, json={"status": "FINISHED"})
    respx.post(f"{base_url}/{user_id}/threads_publish").respond(200, json={"id": "post_transient_500_ok"})

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        result = await client.posts.create(text="Transient 500 test")
        assert result.post_id == "post_transient_500_ok"

    assert mock_sleep.call_count >= 1


@respx.mock
async def test_delete_post(base_url: str, user_id: str, access_token: str) -> None:
    respx.delete(f"{base_url}/post_del_123").respond(200, json={"success": True})

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        success = await client.posts.delete(post_id="post_del_123")
        assert success is True


@respx.mock
async def test_list_posts(base_url: str, user_id: str, access_token: str) -> None:
    respx.get(f"{base_url}/{user_id}/threads").respond(
        200,
        json={
            "data": [
                {"id": "post_1", "text": "Post 1", "timestamp": "2026-09-04T00:00:00+0000", "media_type": "TEXT_POST"},
                {"id": "post_2", "text": "Post 2", "timestamp": "2026-09-04T01:00:00+0000", "media_type": "IMAGE"},
            ],
            "paging": {"cursors": {"after": "next_cursor"}},
        },
    )

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        page = await client.posts.list()
        assert len(page.data) == 2
        assert page.data[0].id == "post_1"
        assert page.data[1].media_type == "IMAGE"


@respx.mock
async def test_iter_posts_pagination(base_url: str, user_id: str, access_token: str) -> None:
    respx.get(f"{base_url}/{user_id}/threads").side_effect = [
        httpx.Response(
            200,
            json={
                "data": [{"id": "post_page1_1", "text": "First"}],
                "paging": {"cursors": {"after": "cur_p1"}, "next": f"{base_url}/{user_id}/threads?after=cur_p1"},
            },
        ),
        httpx.Response(
            200,
            json={
                "data": [{"id": "post_page2_1", "text": "Second"}],
                "paging": {"cursors": {"after": "cur_p2"}},
            },
        ),
        httpx.Response(200, json={"data": []}),
    ]

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        posts = [p async for p in client.posts.iter_posts(limit=1)]
        assert len(posts) == 2
        assert posts[0].id == "post_page1_1"
        assert posts[1].id == "post_page2_1"


@respx.mock
async def test_polling_expired_raises_media_processing_error(
    base_url: str, user_id: str, access_token: str, mocker: pytest_mock.MockerFixture
) -> None:
    mocker.patch("asyncio.sleep")
    respx.post(f"{base_url}/{user_id}/threads").respond(200, json={"id": "cnt_expired"})
    respx.get(f"{base_url}/cnt_expired").respond(200, json={"status": "EXPIRED"})

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        with pytest.raises(ThreadsMediaProcessingError, match=r"expired before processing completed"):
            await client.posts.create(text="Expired test", image_url="https://example.com/img.png")


async def test_create_post_both_image_and_video_raises_validation_error(user_id: str, access_token: str) -> None:
    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        with pytest.raises(ThreadsValidationError, match=r"both image_url and video_url"):
            await client.posts.create(
                text="Conflict",
                image_url="https://example.com/a.jpg",
                video_url="https://example.com/b.mp4",
            )


@respx.mock
async def test_log_masking_does_not_leak_access_token(
    base_url: str, user_id: str, access_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    respx.post(f"{base_url}/{user_id}/threads").respond(400, json={"error": {"message": "Invalid parameter provided"}})

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        with caplog.at_level(logging.ERROR), pytest.raises(ThreadsAPIError):
            await client.posts.create(text="Masking test")

    assert access_token not in caplog.text


@respx.mock
async def test_list_posts_typed_paging(base_url: str, user_id: str, access_token: str) -> None:
    respx.get(f"{base_url}/{user_id}/threads").respond(
        200,
        json={
            "data": [
                {"id": "post_1", "text": "Post 1"},
            ],
            "paging": {
                "cursors": {"before": "cursor_prev", "after": "cursor_next"},
                "next": "https://graph.threads.net/v1.0/me/threads?after=cursor_next",
                "custom_meta_field": "future_field_val",
            },
        },
    )

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        page = await client.posts.list()
        assert isinstance(page.paging, ThreadsPaging)
        assert page.paging.cursors is not None
        assert page.paging.cursors.before == "cursor_prev"
        assert page.paging.cursors.after == "cursor_next"
        assert page.paging.next == "https://graph.threads.net/v1.0/me/threads?after=cursor_next"
        assert page.paging.previous is None
        assert getattr(page.paging, "custom_meta_field", None) == "future_field_val"


@respx.mock
async def test_polling_immediate_finished_no_sleep(
    base_url: str, user_id: str, access_token: str, mocker: pytest_mock.MockerFixture
) -> None:
    mock_sleep = mocker.patch("asyncio.sleep")
    respx.get(f"{base_url}/cnt_fast_1").respond(200, json={"status": "FINISHED"})

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        status = await client.posts.poll_container_status("cnt_fast_1")
        assert status.status == "FINISHED"

    mock_sleep.assert_not_called()


@respx.mock
async def test_polling_retry_sleeps_until_finished(
    base_url: str, user_id: str, access_token: str, mocker: pytest_mock.MockerFixture
) -> None:
    mock_sleep = mocker.patch("asyncio.sleep")
    respx.get(f"{base_url}/cnt_pending_1").side_effect = [
        httpx.Response(200, json={"status": "IN_PROGRESS"}),
        httpx.Response(200, json={"status": "FINISHED"}),
    ]

    async with ThreadsClient(user_id=user_id, access_token=access_token) as client:
        status = await client.posts.poll_container_status("cnt_pending_1")
        assert status.status == "FINISHED"

    assert mock_sleep.call_count == 1
