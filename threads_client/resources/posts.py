from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence

from threads_client.config import (
    DEFAULT_CAROUSEL_CONCURRENCY_LIMIT,
    DEFAULT_PAGE_SIZE,
    DEFAULT_POLL_DELAY_SECONDS,
    DEFAULT_POLL_MAX_ATTEMPTS,
    DEFAULT_PUBLISH_MAX_RETRIES,
    MAX_TOPIC_TAG_LENGTH,
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
    ThreadsPost,
    ThreadsPostPage,
)
from threads_client.resources.base import BaseResource
from threads_client.transport import (
    ParamPrimitive,
    QueryParamsMapping,
    calc_exponential_backoff,
    calc_media_not_ready_backoff,
)

logger = logging.getLogger(__name__)


def sanitize_topic_tag(tag: str | None) -> str | None:
    """Sanitize topic tag by stripping whitespace, hashtags, and prohibited characters."""
    if not tag:
        return None
    cleaned = tag.replace("#", "").replace(".", "").replace("&", "").strip()
    return cleaned[:MAX_TOPIC_TAG_LENGTH] if cleaned else None


class PostsResource(BaseResource):
    """Resource managing Threads posts publishing, lifecycle polling, and retrieval."""

    async def create(
        self,
        text: str,
        *,
        image_url: str | None = None,
        video_url: str | None = None,
        topic_tag: str | None = None,
        reply_to_id: str | None = None,
    ) -> PostCreateResult:
        if image_url and video_url:
            raise ThreadsValidationError("Cannot specify both image_url and video_url.")

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
        *,
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
        *,
        image_url: str | None = None,
        video_url: str | None = None,
        topic_tag: str | None = None,
        reply_to_id: str | None = None,
    ) -> str:
        token = self._require_access_token()
        url = self._resolve_url(f"{self._user_id}/threads")
        media_type = "VIDEO" if video_url else ("IMAGE" if image_url else "TEXT")
        data: dict[str, object] = {
            "media_type": media_type,
            "text": text,
            "access_token": token,
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

        resp = await self._transport.request(
            "POST",
            url,
            data=data,
            extra_secrets=self._get_extra_secrets(),
        )
        container_id = resp.json().get("id")
        if not container_id:
            raise ThreadsAPIError(f"No container ID returned: {resp.text}")
        return str(container_id)

    async def create_carousel_item_container(
        self,
        media_type: str,
        *,
        image_url: str | None = None,
        video_url: str | None = None,
    ) -> str:
        token = self._require_access_token()
        url = self._resolve_url(f"{self._user_id}/threads")
        data: dict[str, object] = {
            "media_type": media_type,
            "is_carousel_item": "true",
            "access_token": token,
        }
        if media_type == "VIDEO" and video_url:
            data["video_url"] = video_url
        elif media_type == "IMAGE" and image_url:
            data["image_url"] = image_url
        else:
            raise ThreadsValidationError(f"Invalid media payload for {media_type}")

        resp = await self._transport.request(
            "POST",
            url,
            data=data,
            extra_secrets=self._get_extra_secrets(),
        )
        container_id = resp.json().get("id")
        if not container_id:
            raise ThreadsAPIError(f"No item container ID returned: {resp.text}")
        return str(container_id)

    async def create_carousel_container(
        self,
        text: str,
        children: Sequence[str],
        *,
        topic_tag: str | None = None,
        reply_to_id: str | None = None,
    ) -> str:
        if not children:
            raise ThreadsValidationError("Carousel children cannot be empty")
        token = self._require_access_token()
        url = self._resolve_url(f"{self._user_id}/threads")
        data: dict[str, object] = {
            "media_type": "CAROUSEL",
            "children": ",".join(children),
            "text": text,
            "access_token": token,
        }
        tag = sanitize_topic_tag(topic_tag)
        if tag:
            data["topic_tag"] = tag
        if reply_to_id:
            data["reply_to_id"] = reply_to_id

        resp = await self._transport.request(
            "POST",
            url,
            data=data,
            extra_secrets=self._get_extra_secrets(),
        )
        container_id = resp.json().get("id")
        if not container_id:
            raise ThreadsAPIError(f"No carousel container ID returned: {resp.text}")
        return str(container_id)

    async def poll_container_status(
        self,
        container_id: str,
        *,
        max_attempts: int = DEFAULT_POLL_MAX_ATTEMPTS,
        delay: int = DEFAULT_POLL_DELAY_SECONDS,
    ) -> ContainerStatus:
        token = self._require_access_token()
        url = self._resolve_url(container_id)
        params: QueryParamsMapping = {"fields": "status,error_message", "access_token": token}

        for attempt in range(max_attempts):
            resp = await self._transport.request(
                "GET",
                url,
                params=params,
                max_retries=1,
                extra_secrets=self._get_extra_secrets(),
            )
            data = resp.json()
            status = data.get("status")

            if status == "FINISHED":
                return ContainerStatus(id=container_id, status="FINISHED")
            if status == "EXPIRED":
                raise ThreadsMediaProcessingError(f"Container {container_id} expired before processing completed.")
            if status == "ERROR":
                err_msg = str(data.get("error_message") or "Container processing failed")
                raise ThreadsMediaProcessingError(f"Container processing failed: {err_msg}")

            logger.info("Container %s status: %s (%s/%s)", container_id, status, attempt + 1, max_attempts)
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)

        raise ThreadsTimeoutError(f"Container {container_id} did not finish processing in time.")

    async def publish_container(
        self,
        container_id: str,
        *,
        max_retries: int = DEFAULT_PUBLISH_MAX_RETRIES,
    ) -> str:
        token = self._require_access_token()
        url = self._resolve_url(f"{self._user_id}/threads_publish")
        data: dict[str, object] = {"creation_id": container_id, "access_token": token}

        for attempt in range(max_retries):
            try:
                resp = await self._transport.request(
                    "POST",
                    url,
                    data=data,
                    max_retries=1,
                    extra_secrets=self._get_extra_secrets(),
                )
                post_id = resp.json().get("id")
                if not post_id:
                    raise ThreadsAPIError(f"No publish ID returned: {resp.text}")
                return str(post_id)
            except ThreadsAPIError as error:
                if (not error.is_media_not_ready and not error.is_transient) or attempt >= max_retries - 1:
                    raise
                wait_sec = (
                    calc_media_not_ready_backoff(attempt)
                    if error.is_media_not_ready
                    else calc_exponential_backoff(attempt)
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
        token = self._require_access_token()
        url = self._resolve_url(post_id)
        params: QueryParamsMapping = {"access_token": token}
        resp = await self._transport.request(
            "DELETE",
            url,
            params=params,
            extra_secrets=self._get_extra_secrets(),
        )
        data = resp.json()
        return bool(data.get("success", False))

    async def list(
        self,
        *,
        user_id: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        after: str | None = None,
    ) -> ThreadsPostPage:
        token = self._require_access_token()
        target_uid = user_id or self._user_id
        url = self._resolve_url(f"{target_uid}/threads")
        params_dict: dict[str, ParamPrimitive] = {
            "fields": "id,text,timestamp,media_type,permalink",
            "limit": limit,
            "access_token": token,
        }
        if after:
            params_dict["after"] = after

        resp = await self._transport.request(
            "GET",
            url,
            params=params_dict,
            extra_secrets=self._get_extra_secrets(),
        )
        return ThreadsPostPage.model_validate(resp.json())

    async def iter_posts(
        self,
        *,
        user_id: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncIterator[ThreadsPost]:
        after: str | None = None
        while True:
            page = await self.list(user_id=user_id, limit=limit, after=after)
            if not page.data:
                break
            for post in page.data:
                yield post
            if not page.paging or not page.paging.cursors or not page.paging.cursors.after:
                break
            after = page.paging.cursors.after
