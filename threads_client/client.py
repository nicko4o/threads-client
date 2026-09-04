from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from types import TracebackType

import httpx

from threads_client.config import (
    DEFAULT_CAROUSEL_CONCURRENCY_LIMIT,
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_POLL_DELAY_SECONDS,
    DEFAULT_POLL_MAX_ATTEMPTS,
    DEFAULT_PUBLISH_MAX_RETRIES,
    DEFAULT_REQUEST_MAX_RETRIES,
    DEFAULT_THREADS_API_HOST,
    DEFAULT_TIMEOUT_SECONDS,
    LOG_RESPONSE_BODY_LIMIT,
    MAX_TOPIC_TAG_LENGTH,
    MEDIA_NOT_READY_BACKOFF_FACTOR_SECONDS,
)
from threads_client.exceptions import (
    ThreadsAPIError,
    ThreadsMediaProcessingError,
    ThreadsTimeoutError,
    ThreadsValidationError,
)
from threads_client.models import (
    CarouselMediaItem,
    ContainerStatus,
    PostCreateResult,
    ThreadsPostPage,
    TokenInfo,
)

logger = logging.getLogger(__name__)

ParamPrimitive = str | int | float | bool | None
QueryParamsMapping = Mapping[str, ParamPrimitive | Sequence[ParamPrimitive]]


def sanitize_topic_tag(tag: str | None) -> str | None:
    if not tag:
        return None
    cleaned = tag.replace(".", "").replace("&", "").strip()
    return cleaned[:MAX_TOPIC_TAG_LENGTH] if cleaned else None


class BaseResource:
    """Base class for API resources with retry engine and token masking."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str = DEFAULT_THREADS_API_HOST,
        access_token: str = "",
        user_id: str = "",
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._user_id = user_id

    def _resolve_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        return f"{self._base_url}/{path_or_url.lstrip('/')}"

    async def _send_with_retry(
        self,
        method: str,
        url: str,
        data: dict[str, object] | None = None,
        params: QueryParamsMapping | None = None,
        max_retries: int = DEFAULT_REQUEST_MAX_RETRIES,
    ) -> httpx.Response:
        for attempt in range(max_retries):
            try:
                resp = await self._send_single(method, url, data=data, params=params)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as error:
                api_error = ThreadsAPIError.from_http_error(error)
                self._log_http_error(method, url, error)
                if not api_error.is_transient or attempt >= max_retries - 1:
                    raise api_error from error
                await asyncio.sleep(2**attempt)
            except httpx.RequestError as error:
                if attempt >= max_retries - 1:
                    raise ThreadsAPIError(f"Network request failed: {error}") from error
                await asyncio.sleep(2**attempt)
        raise ThreadsAPIError("Request failed after retries")

    async def _send_single(
        self,
        method: str,
        url: str,
        data: dict[str, object] | None = None,
        params: QueryParamsMapping | None = None,
    ) -> httpx.Response:
        if method.upper() == "POST":
            return await self._client.post(url, data=data)
        if method.upper() == "DELETE":
            return await self._client.delete(url, params=params)
        return await self._client.get(url, params=params)

    def _log_http_error(self, method: str, url: str, error: httpx.HTTPStatusError) -> None:
        resp = error.response
        if resp is None:
            return
        masked_text = resp.text.replace(self._access_token, "[REDACTED]") if self._access_token else resp.text
        logger.error(
            "HTTP request failed method=%s url=%s status=%s body=%s",
            method.upper(),
            url,
            resp.status_code,
            masked_text[:LOG_RESPONSE_BODY_LIMIT],
        )


class TokensResource(BaseResource):
    """Resource managing OAuth tokens exchange and renewal."""

    async def exchange(self, short_token: str, app_secret: str) -> TokenInfo:
        url = self._resolve_url("access_token")
        params: QueryParamsMapping = {
            "grant_type": "th_exchange_token",
            "client_secret": app_secret,
            "access_token": short_token,
        }
        resp = await self._send_with_retry("GET", url, params=params)
        data = resp.json()
        return TokenInfo.model_validate(data)

    async def refresh(self, long_token: str) -> TokenInfo:
        url = self._resolve_url("refresh_access_token")
        params: QueryParamsMapping = {
            "grant_type": "th_refresh_token",
            "access_token": long_token,
        }
        resp = await self._send_with_retry("GET", url, params=params)
        data = resp.json()
        return TokenInfo.model_validate(data)


class PostsResource(BaseResource):
    """Resource managing Threads posts publishing, lifecycle polling, and deletion."""

    async def create(
        self,
        text: str,
        image_url: str | None = None,
        video_url: str | None = None,
        topic_tag: str | None = None,
        reply_to_id: str | None = None,
    ) -> PostCreateResult:
        container_id = await self.create_container(
            text=text,
            image_url=image_url,
            video_url=video_url,
            topic_tag=topic_tag,
            reply_to_id=reply_to_id,
        )
        await self.poll_container_status(container_id)
        post_id = await self.publish_container(container_id)
        return PostCreateResult(post_id=post_id, container_id=container_id)

    async def create_carousel(
        self,
        text: str,
        items: Sequence[CarouselMediaItem],
        topic_tag: str | None = None,
        reply_to_id: str | None = None,
        concurrency_limit: int = DEFAULT_CAROUSEL_CONCURRENCY_LIMIT,
    ) -> PostCreateResult:
        if not items:
            raise ThreadsValidationError("Carousel items cannot be empty")

        sem = asyncio.Semaphore(concurrency_limit)

        async def _upload_item(item: CarouselMediaItem) -> str:
            async with sem:
                img = item.url if item.media_type == "IMAGE" else None
                vid = item.url if item.media_type == "VIDEO" else None
                return await self.create_carousel_item_container(item.media_type, image_url=img, video_url=vid)

        child_ids = list(await asyncio.gather(*(_upload_item(it) for it in items)))
        await asyncio.gather(*(self.poll_container_status(cid) for cid in child_ids))

        parent_id = await self.create_carousel_container(
            text=text,
            children=child_ids,
            topic_tag=topic_tag,
            reply_to_id=reply_to_id,
        )
        await self.poll_container_status(parent_id)
        post_id = await self.publish_container(parent_id)
        return PostCreateResult(post_id=post_id, container_id=parent_id)

    async def create_container(
        self,
        text: str,
        image_url: str | None = None,
        video_url: str | None = None,
        topic_tag: str | None = None,
        reply_to_id: str | None = None,
    ) -> str:
        url = self._resolve_url(f"{self._user_id}/threads")
        media_type = "VIDEO" if video_url else ("IMAGE" if image_url else "TEXT")
        data: dict[str, object] = {
            "media_type": media_type,
            "text": text,
            "access_token": self._access_token,
        }
        if video_url:
            data["video_url"] = video_url
        elif image_url:
            data["image_url"] = image_url

        tag = sanitize_topic_tag(topic_tag)
        if tag:
            data["topic_tag"] = tag
        if reply_to_id:
            data["reply_to_id"] = reply_to_id

        resp = await self._send_with_retry("POST", url, data=data)
        container_id = resp.json().get("id")
        if not container_id:
            raise ThreadsAPIError(f"No container ID returned: {resp.text}")
        return str(container_id)

    async def create_carousel_item_container(
        self,
        media_type: str,
        image_url: str | None = None,
        video_url: str | None = None,
    ) -> str:
        url = self._resolve_url(f"{self._user_id}/threads")
        data: dict[str, object] = {
            "media_type": media_type,
            "is_carousel_item": "true",
            "access_token": self._access_token,
        }
        if media_type == "VIDEO" and video_url:
            data["video_url"] = video_url
        elif media_type == "IMAGE" and image_url:
            data["image_url"] = image_url
        else:
            raise ThreadsValidationError(f"Invalid media payload for {media_type}")

        resp = await self._send_with_retry("POST", url, data=data)
        container_id = resp.json().get("id")
        if not container_id:
            raise ThreadsAPIError(f"No item container ID returned: {resp.text}")
        return str(container_id)

    async def create_carousel_container(
        self,
        text: str,
        children: Sequence[str],
        topic_tag: str | None = None,
        reply_to_id: str | None = None,
    ) -> str:
        if not children:
            raise ThreadsValidationError("Carousel children cannot be empty")
        url = self._resolve_url(f"{self._user_id}/threads")
        data: dict[str, object] = {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "text": text,
            "access_token": self._access_token,
        }
        tag = sanitize_topic_tag(topic_tag)
        if tag:
            data["topic_tag"] = tag
        if reply_to_id:
            data["reply_to_id"] = reply_to_id

        resp = await self._send_with_retry("POST", url, data=data)
        container_id = resp.json().get("id")
        if not container_id:
            raise ThreadsAPIError(f"No carousel container ID returned: {resp.text}")
        return str(container_id)

    async def poll_container_status(
        self,
        container_id: str,
        max_attempts: int = DEFAULT_POLL_MAX_ATTEMPTS,
        delay: int = DEFAULT_POLL_DELAY_SECONDS,
    ) -> ContainerStatus:
        url = self._resolve_url(container_id)
        params: QueryParamsMapping = {"fields": "status,error_message", "access_token": self._access_token}

        for attempt in range(max_attempts):
            resp = await self._send_with_retry("GET", url, params=params, max_retries=1)
            data = resp.json()
            status = data.get("status")

            if status == "FINISHED":
                return ContainerStatus(id=container_id, status="FINISHED")
            if status == "ERROR":
                err_msg = str(data.get("error_message") or "Container processing failed")
                raise ThreadsMediaProcessingError(f"Container processing failed: {err_msg}")
            logger.info("Container %s status: %s (%s/%s)", container_id, status, attempt + 1, max_attempts)

            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)

        raise ThreadsTimeoutError(f"Container {container_id} did not finish processing in time.")

    async def publish_container(self, container_id: str, max_retries: int = DEFAULT_PUBLISH_MAX_RETRIES) -> str:
        url = self._resolve_url(f"{self._user_id}/threads_publish")
        data: dict[str, object] = {"creation_id": container_id, "access_token": self._access_token}

        for attempt in range(max_retries):
            try:
                resp = await self._send_with_retry("POST", url, data=data, max_retries=1)
                post_id = resp.json().get("id")
                if not post_id:
                    raise ThreadsAPIError(f"No publish ID returned: {resp.text}")
                return str(post_id)
            except ThreadsAPIError as error:
                if (not error.is_media_not_ready and not error.is_transient) or attempt >= max_retries - 1:
                    raise
                wait_sec = (
                    MEDIA_NOT_READY_BACKOFF_FACTOR_SECONDS * (attempt + 1) if error.is_media_not_ready else 2**attempt
                )
                logger.warning(
                    "Publish retry container=%s wait=%ss (%s/%s)",
                    container_id,
                    wait_sec,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(wait_sec)

        raise ThreadsAPIError(f"Failed to publish container {container_id} after retries")

    async def delete(self, post_id: str) -> bool:
        url = self._resolve_url(post_id)
        params: QueryParamsMapping = {"access_token": self._access_token}
        resp = await self._send_with_retry("DELETE", url, params=params)
        data = resp.json()
        return bool(data.get("success", False))

    async def list(
        self,
        user_id: str | None = None,
        limit: int = 25,
        after: str | None = None,
    ) -> ThreadsPostPage:
        target_uid = user_id or self._user_id
        url = self._resolve_url(f"{target_uid}/threads")
        params_dict: dict[str, ParamPrimitive] = {
            "fields": "id,text,timestamp,media_type,permalink",
            "limit": limit,
            "access_token": self._access_token,
        }
        if after:
            params_dict["after"] = after

        resp = await self._send_with_retry("GET", url, params=params_dict)
        data = resp.json()
        return ThreadsPostPage.model_validate(data)

    async def find_by_signature(self, signature: str, user_id: str | None = None) -> str | None:
        page = await self.list(user_id=user_id, limit=25)
        for post in page.data:
            if post.text and signature in post.text:
                return post.id
        return None


class ThreadsClient:
    """Async-first client for Meta Threads Graph API."""

    def __init__(
        self,
        user_id: str,
        access_token: str,
        base_url: str = DEFAULT_THREADS_API_HOST,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    ) -> None:
        self.user_id = user_id
        self.access_token = access_token
        self.base_url = base_url.rstrip("/")

        self._own_client = client is None
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=connect_timeout))

        self.posts = PostsResource(
            client=self._client,
            base_url=self.base_url,
            access_token=self.access_token,
            user_id=self.user_id,
        )
        self.tokens = TokensResource(
            client=self._client,
            base_url=self.base_url,
            access_token=self.access_token,
            user_id=self.user_id,
        )

    async def close(self) -> None:
        if self._own_client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> ThreadsClient:
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def post(
        self,
        text: str,
        topic_tag: str | None = None,
        reply_to_id: str | None = None,
        image_url: str | None = None,
        video_url: str | None = None,
    ) -> str:
        result = await self.posts.create(
            text=text,
            topic_tag=topic_tag,
            reply_to_id=reply_to_id,
            image_url=image_url,
            video_url=video_url,
        )
        return result.post_id

    async def post_carousel(
        self,
        text: str,
        items: Sequence[CarouselMediaItem],
        topic_tag: str | None = None,
        reply_to_id: str | None = None,
    ) -> str:
        result = await self.posts.create_carousel(
            text=text,
            items=items,
            topic_tag=topic_tag,
            reply_to_id=reply_to_id,
        )
        return result.post_id

    async def delete_post(self, post_id: str) -> bool:
        return await self.posts.delete(post_id)
