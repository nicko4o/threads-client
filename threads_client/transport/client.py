from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from typing import Literal

import httpx

from threads_client.config import DEFAULT_REQUEST_MAX_RETRIES, LOG_RESPONSE_BODY_LIMIT
from threads_client.exceptions import ThreadsAPIError
from threads_client.transport.redaction import mask_text, mask_url
from threads_client.transport.retry import calc_exponential_backoff, calc_media_not_ready_backoff

logger = logging.getLogger(__name__)

ParamPrimitive = str | int | float | bool | None
QueryParamsMapping = Mapping[str, ParamPrimitive | Sequence[ParamPrimitive]]
HTTPMethod = Literal["GET", "POST", "DELETE"]

_VALID_METHODS: frozenset[str] = frozenset({"GET", "POST", "DELETE"})


class Transport:
    """Async HTTP transport engine with automatic retries and secret redaction."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def request(
        self,
        method: HTTPMethod,
        url: str,
        *,
        data: dict[str, object] | None = None,
        params: QueryParamsMapping | None = None,
        max_retries: int = DEFAULT_REQUEST_MAX_RETRIES,
        extra_secrets: Sequence[str] = (),
    ) -> httpx.Response:
        norm_method = method.upper()
        if norm_method not in _VALID_METHODS:
            raise ValueError(f"Unsupported HTTP method: {method}")

        post_data = data if norm_method == "POST" else None
        retries = max(1, max_retries)

        for attempt in range(retries):
            try:
                resp = await self._client.request(norm_method, url, data=post_data, params=params)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as error:
                api_error = ThreadsAPIError.from_http_error(error)
                self._log_http_error(norm_method, url, error, extra_secrets)
                if not api_error.is_transient or attempt >= retries - 1:
                    raise api_error from error
                await self._retry_delay(attempt, retries, norm_method, url, api_error, extra_secrets)
            except httpx.RequestError as error:
                self._log_request_error(norm_method, url, error, extra_secrets)
                if attempt >= retries - 1:
                    raise ThreadsAPIError(f"Network request failed: {error}", is_transient=True) from error
                await self._retry_delay(attempt, retries, norm_method, url, error, extra_secrets)

        raise ThreadsAPIError("Request failed after retries")

    async def _retry_delay(
        self,
        attempt: int,
        retries: int,
        method: str,
        url: str,
        error: Exception,
        extra_secrets: Sequence[str],
    ) -> None:
        is_media_delay = isinstance(error, ThreadsAPIError) and error.is_media_processing_delay
        wait_sec = calc_media_not_ready_backoff(attempt) if is_media_delay else calc_exponential_backoff(attempt)
        masked_err = mask_text(str(error), extra_secrets)
        logger.warning(
            "Retry request method=%s url=%s attempt=%s/%s wait=%.1fs error=%s",
            method,
            mask_url(url),
            attempt + 1,
            retries,
            wait_sec,
            masked_err,
        )
        await asyncio.sleep(wait_sec)

    def _log_http_error(
        self,
        method: str,
        url: str,
        error: httpx.HTTPStatusError,
        extra_secrets: Sequence[str],
    ) -> None:
        resp = error.response
        if resp is None:
            return
        masked_url = mask_url(url)
        masked_text = mask_text(resp.text, extra_secrets)
        logger.error(
            "HTTP request failed method=%s url=%s status=%s body=%s",
            method,
            masked_url,
            resp.status_code,
            masked_text[:LOG_RESPONSE_BODY_LIMIT],
        )

    def _log_request_error(
        self,
        method: str,
        url: str,
        error: httpx.RequestError,
        extra_secrets: Sequence[str],
    ) -> None:
        masked_url = mask_url(url)
        masked_msg = mask_text(str(error), extra_secrets)
        logger.error("HTTP request error method=%s url=%s error=%s", method, masked_url, masked_msg)
