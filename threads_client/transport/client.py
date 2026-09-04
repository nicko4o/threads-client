from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from typing import Literal

import httpx

from threads_client.config import DEFAULT_REQUEST_MAX_RETRIES, LOG_RESPONSE_BODY_LIMIT
from threads_client.exceptions import ThreadsAPIError
from threads_client.transport.redaction import mask_text, mask_url
from threads_client.transport.retry import calc_exponential_backoff

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

        for attempt in range(max_retries):
            try:
                resp = await self._send_single(norm_method, url, data=data, params=params)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as error:
                api_error = ThreadsAPIError.from_http_error(error)
                self._log_http_error(norm_method, url, error, extra_secrets)
                if not api_error.is_transient or attempt >= max_retries - 1:
                    raise api_error from error
                await asyncio.sleep(calc_exponential_backoff(attempt))
            except httpx.RequestError as error:
                self._log_request_error(norm_method, url, error, extra_secrets)
                if attempt >= max_retries - 1:
                    raise ThreadsAPIError(f"Network request failed: {error}") from error
                await asyncio.sleep(calc_exponential_backoff(attempt))

        raise ThreadsAPIError("Request failed after retries")

    async def _send_single(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, object] | None = None,
        params: QueryParamsMapping | None = None,
    ) -> httpx.Response:
        if method == "POST":
            return await self._client.post(url, data=data)
        if method == "DELETE":
            return await self._client.delete(url, params=params)
        if method == "GET":
            return await self._client.get(url, params=params)
        raise ValueError(f"Unsupported HTTP method: {method}")

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
