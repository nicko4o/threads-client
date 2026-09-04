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

    assert api_err.status_code == 400
    assert api_err.code == 24
    assert api_err.subcode == 4279009
    assert api_err.is_transient is False
    assert api_err.is_media_not_ready is True
    assert "The media resource is not ready" in str(api_err)


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
