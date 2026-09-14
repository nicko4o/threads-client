from __future__ import annotations

import httpx

from threads_client.exceptions import (
    ThreadsAPIError,
    ThreadsAuthenticationError,
    ThreadsError,
    ThreadsMediaProcessingError,
    ThreadsRateLimitError,
    ThreadsTimeoutError,
    ThreadsValidationError,
)


def test_exception_hierarchy() -> None:
    assert issubclass(ThreadsAPIError, ThreadsError)
    assert issubclass(ThreadsAuthenticationError, ThreadsAPIError)
    assert issubclass(ThreadsRateLimitError, ThreadsAPIError)
    assert issubclass(ThreadsMediaProcessingError, ThreadsAPIError)
    assert issubclass(ThreadsTimeoutError, ThreadsError)
    assert issubclass(ThreadsValidationError, ThreadsError)


def test_threads_api_error_parsing() -> None:
    request = httpx.Request("POST", "https://graph.threads.net/v1.0/me/threads")
    response = httpx.Response(
        status_code=400,
        request=request,
        json={
            "error": {
                "message": "The media resource is not ready",
                "type": "OAuthException",
                "code": 24,
                "error_subcode": 4279009,
                "is_transient": False,
            }
        },
    )
    http_err = httpx.HTTPStatusError("Bad Request", request=request, response=response)
    api_err = ThreadsAPIError.from_http_error(http_err)

    assert isinstance(api_err, ThreadsMediaProcessingError)
    assert api_err.status_code == 400
    assert api_err.code == 24
    assert api_err.subcode == 4279009
    assert api_err.is_transient is True
    assert api_err.is_media_not_ready is True
    assert api_err.is_media_processing_delay is True
    assert "The media resource is not ready" in str(api_err)


def test_threads_api_error_carousel_child_not_ready_4279004() -> None:
    request = httpx.Request("POST", "https://graph.threads.net/v1.0/me/threads")
    response = httpx.Response(
        status_code=400,
        request=request,
        json={
            "error": {
                "message": "Invalid carousel children",
                "type": "OAuthException",
                "code": 100,
                "error_subcode": 4279004,
                "is_transient": False,
            }
        },
    )
    http_err = httpx.HTTPStatusError("Bad Request", request=request, response=response)
    api_err = ThreadsAPIError.from_http_error(http_err)

    assert isinstance(api_err, ThreadsMediaProcessingError)
    assert api_err.status_code == 400
    assert api_err.code == 100
    assert api_err.subcode == 4279004
    assert api_err.is_transient is True
    assert api_err.is_carousel_child_not_ready is True
    assert api_err.is_media_processing_delay is True


def test_threads_api_rate_limit_codes() -> None:
    request = httpx.Request("GET", "https://graph.threads.net/v1.0/me")
    for code in (32, 613):
        response = httpx.Response(
            status_code=400,
            request=request,
            json={"error": {"message": f"Rate limited {code}", "code": code}},
        )
        api_err = ThreadsAPIError.from_http_error(
            httpx.HTTPStatusError(f"Rate limited {code}", request=request, response=response)
        )
        assert isinstance(api_err, ThreadsRateLimitError)
        assert api_err.is_transient is True


def test_threads_api_error_message_truncation() -> None:
    request = httpx.Request("GET", "https://graph.threads.net/v1.0/me")
    huge_html = "A" * 1000
    response = httpx.Response(status_code=502, request=request, text=huge_html)
    err = ThreadsAPIError.from_http_error(httpx.HTTPStatusError("502 Error", request=request, response=response))
    assert len(err.message) == 503  # 500 + "..."
    assert err.message.endswith("...")


def test_threads_api_error_transient_detection() -> None:
    request = httpx.Request("GET", "https://graph.threads.net/v1.0/me")
    response_500 = httpx.Response(status_code=500, request=request, json={"error": {"message": "Server Error"}})
    err_500 = ThreadsAPIError.from_http_error(
        httpx.HTTPStatusError("Server Error", request=request, response=response_500)
    )
    assert err_500.is_transient is True

    response_transient = httpx.Response(
        status_code=400,
        request=request,
        json={"error": {"message": "Temporary failure", "code": 2, "is_transient": True}},
    )
    err_transient = ThreadsAPIError.from_http_error(
        httpx.HTTPStatusError("Temp failure", request=request, response=response_transient)
    )
    assert err_transient.is_transient is True


def test_threads_api_error_from_html_gateway_response() -> None:
    request = httpx.Request("GET", "https://graph.threads.net/v1.0/me")
    html_content = "<html><body>502 Bad Gateway</body></html>"
    response_html = httpx.Response(status_code=502, request=request, text=html_content)
    err = ThreadsAPIError.from_http_error(
        httpx.HTTPStatusError("502 Server Error", request=request, response=response_html)
    )

    assert err.status_code == 502
    assert err.message == html_content
    assert err.is_transient is True


def test_threads_api_error_from_invalid_json_fallback() -> None:
    request = httpx.Request("POST", "https://graph.threads.net/v1.0/me/threads")
    response_invalid_json = httpx.Response(
        status_code=500,
        request=request,
        content=b"\xff\xfe\xfd",
        headers={"Content-Type": "application/json"},
    )
    err = ThreadsAPIError.from_http_error(
        httpx.HTTPStatusError("500 Server Error", request=request, response=response_invalid_json)
    )

    assert err.status_code == 500
    assert err.is_transient is True
