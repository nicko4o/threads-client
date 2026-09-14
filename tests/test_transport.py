from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_mock
import respx

from threads_client.exceptions import ThreadsAPIError
from threads_client.transport.client import Transport


@pytest.fixture
async def transport() -> AsyncIterator[Transport]:
    async with httpx.AsyncClient() as client:
        yield Transport(client)


@respx.mock
async def test_transport_post_with_query_params(transport: Transport) -> None:
    test_url = "https://graph.threads.net/v1.0/test_endpoint"
    route = respx.post(test_url).respond(200, json={"id": "success_1"})

    resp = await transport.request(
        "POST",
        test_url,
        data={"body_key": "body_val"},
        params={"param_key": "param_val"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"id": "success_1"}

    assert route.called
    last_req = route.calls.last.request
    assert "param_key=param_val" in str(last_req.url)
    assert b"body_key=body_val" in last_req.content


@respx.mock
async def test_transport_all_verbs(transport: Transport) -> None:
    base_url = "https://graph.threads.net/v1.0"
    get_route = respx.get(f"{base_url}/get_test").respond(200, json={"ok": True})
    post_route = respx.post(f"{base_url}/post_test").respond(200, json={"posted": True})
    delete_route = respx.delete(f"{base_url}/del_test").respond(200, json={"deleted": True})

    r_get = await transport.request("GET", f"{base_url}/get_test", params={"q": "1"})
    assert r_get.status_code == 200
    assert "q=1" in str(get_route.calls.last.request.url)

    r_post = await transport.request("POST", f"{base_url}/post_test", data={"k": "v"})
    assert r_post.status_code == 200
    assert b"k=v" in post_route.calls.last.request.content

    r_del = await transport.request("DELETE", f"{base_url}/del_test", params={"force": "true"})
    assert r_del.status_code == 200
    assert "force=true" in str(delete_route.calls.last.request.url)


async def test_transport_unsupported_method(transport: Transport) -> None:
    with pytest.raises(ValueError, match="Unsupported HTTP method"):
        await transport.request("PUT", "https://graph.threads.net/v1.0/test")  # type: ignore[arg-type]


@respx.mock
async def test_transport_transient_retry(transport: Transport, mocker: pytest_mock.MockerFixture) -> None:
    mock_sleep = mocker.patch("asyncio.sleep")
    test_url = "https://graph.threads.net/v1.0/flaky"
    route = respx.get(test_url)
    route.side_effect = [
        httpx.Response(500, request=httpx.Request("GET", test_url)),
        httpx.Response(200, json={"recovered": True}, request=httpx.Request("GET", test_url)),
    ]

    resp = await transport.request("GET", test_url, max_retries=3)
    assert resp.status_code == 200
    assert resp.json() == {"recovered": True}
    assert route.call_count == 2
    mock_sleep.assert_called_once_with(1.0)


@respx.mock
async def test_transport_media_delay_retry_backoff(transport: Transport, mocker: pytest_mock.MockerFixture) -> None:
    mock_sleep = mocker.patch("asyncio.sleep")
    test_url = "https://graph.threads.net/v1.0/media_retry"
    route = respx.post(test_url)
    route.side_effect = [
        httpx.Response(
            400,
            json={"error": {"message": "Carousel child not ready", "code": 100, "error_subcode": 4279004}},
            request=httpx.Request("POST", test_url),
        ),
        httpx.Response(200, json={"id": "cnt_ok"}, request=httpx.Request("POST", test_url)),
    ]

    resp = await transport.request("POST", test_url, max_retries=3)
    assert resp.status_code == 200
    assert resp.json() == {"id": "cnt_ok"}
    assert route.call_count == 2
    mock_sleep.assert_called_once_with(3.0)  # calc_media_not_ready_backoff(0) = 3s


@respx.mock
async def test_transport_network_error_retry(transport: Transport, mocker: pytest_mock.MockerFixture) -> None:
    mock_sleep = mocker.patch("asyncio.sleep")
    test_url = "https://graph.threads.net/v1.0/network_flaky"
    route = respx.get(test_url)
    route.side_effect = [
        httpx.ConnectError("Connection reset", request=httpx.Request("GET", test_url)),
        httpx.Response(200, json={"recovered": True}, request=httpx.Request("GET", test_url)),
    ]

    resp = await transport.request("GET", test_url, max_retries=3)
    assert resp.status_code == 200
    assert resp.json() == {"recovered": True}
    assert route.call_count == 2
    mock_sleep.assert_called_once_with(1.0)


@respx.mock
async def test_transport_non_transient_fail_fast(transport: Transport, mocker: pytest_mock.MockerFixture) -> None:
    mock_sleep = mocker.patch("asyncio.sleep")
    test_url = "https://graph.threads.net/v1.0/bad_param"
    route = respx.get(test_url).respond(
        400,
        json={"error": {"message": "Invalid parameter", "code": 100, "is_transient": False}},
    )

    with pytest.raises(ThreadsAPIError) as exc_info:
        await transport.request("GET", test_url, max_retries=3)
    assert exc_info.value.code == 100
    assert route.call_count == 1
    mock_sleep.assert_not_called()


@respx.mock
async def test_transport_exhausted_retries(transport: Transport, mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch("asyncio.sleep")
    test_url = "https://graph.threads.net/v1.0/down"
    respx.get(test_url).respond(503)

    with pytest.raises(ThreadsAPIError) as exc_info:
        await transport.request("GET", test_url, max_retries=2)
    assert exc_info.value.status_code == 503


@respx.mock
async def test_transport_gateway_error_retry_and_fallback(
    transport: Transport, mocker: pytest_mock.MockerFixture
) -> None:
    mock_sleep = mocker.patch("asyncio.sleep")
    test_url = "https://graph.threads.net/v1.0/gateway"
    route = respx.get(test_url)
    route.side_effect = [
        httpx.Response(502, text="<html>502 Bad Gateway</html>", request=httpx.Request("GET", test_url)),
        httpx.Response(200, json={"recovered": True}, request=httpx.Request("GET", test_url)),
    ]

    resp = await transport.request("GET", test_url, max_retries=3)
    assert resp.status_code == 200
    assert resp.json() == {"recovered": True}
    assert route.call_count == 2
    mock_sleep.assert_called_once_with(1.0)
