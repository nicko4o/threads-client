from __future__ import annotations

from collections.abc import Sequence
from types import TracebackType

import httpx

from threads_client.config import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_THREADS_API_HOST,
    DEFAULT_TIMEOUT_SECONDS,
)
from threads_client.models import CarouselMediaItem
from threads_client.resources import (
    BaseResource,
    ClientContext,
    PostsResource,
    TokensResource,
    sanitize_topic_tag,
)
from threads_client.transport import Transport

__all__ = [
    "BaseResource",
    "ClientContext",
    "PostsResource",
    "ThreadsClient",
    "TokensResource",
    "sanitize_topic_tag",
]


class ThreadsClient:
    """Async-first client for Meta Threads Graph API."""

    def __init__(
        self,
        access_token: str | None = None,
        user_id: str = "me",
        *,
        base_url: str = DEFAULT_THREADS_API_HOST,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    ) -> None:
        self._context = ClientContext(
            user_id=user_id,
            access_token=access_token,
            base_url=base_url.rstrip("/"),
        )
        self._own_client = client is None
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=connect_timeout))
        self._transport = Transport(self._client)

        self.posts = PostsResource(
            transport=self._transport,
            context=self._context,
        )
        self.tokens = TokensResource(
            transport=self._transport,
            context=self._context,
        )

    @property
    def access_token(self) -> str | None:
        """OAuth access token (Single Source of Truth shared with resources)."""
        return self._context.access_token

    @access_token.setter
    def access_token(self, value: str | None) -> None:
        self._context.access_token = value

    @property
    def user_id(self) -> str:
        """Target Threads user ID (defaults to 'me')."""
        return self._context.user_id

    @user_id.setter
    def user_id(self, value: str) -> None:
        self._context.user_id = value

    @property
    def base_url(self) -> str:
        """Base API host URL."""
        return self._context.base_url

    @base_url.setter
    def base_url(self, value: str) -> None:
        self._context.base_url = value.rstrip("/")

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
        *,
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
        *,
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
