from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

MediaType = Literal["TEXT", "IMAGE", "VIDEO", "CAROUSEL"]
CarouselItemMediaType = Literal["IMAGE", "VIDEO"]
ContainerStatusState = Literal["EXPIRED", "ERROR", "FINISHED", "IN_PROGRESS", "PUBLISHED"]


class CarouselMediaItem(BaseModel):
    media_type: CarouselItemMediaType = Field(description="Media type for carousel item: IMAGE or VIDEO")
    url: str = Field(description="Publicly accessible URL of the media asset")


class ContainerStatus(BaseModel):
    id: str
    status: str
    error_message: str | None = None


class PostCreateResult(BaseModel):
    post_id: str = Field(description="Published Threads post ID")
    container_id: str = Field(description="Underlying creation container ID")


class ThreadsPost(BaseModel):
    id: str
    text: str | None = None
    timestamp: str | None = None
    media_type: str | None = None
    permalink: str | None = None


class ThreadsPostPage(BaseModel):
    data: list[ThreadsPost] = Field(default_factory=list)
    paging: dict[str, Any] | None = None


class TokenInfo(BaseModel):
    access_token: str = Field(description="OAuth access token")
    token_type: str = Field(default="bearer", description="Token type, usually bearer")
    expires_in: int | None = Field(default=None, description="Expiration in seconds")
