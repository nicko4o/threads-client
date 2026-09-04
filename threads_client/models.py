from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MediaType = Literal["TEXT", "IMAGE", "VIDEO", "CAROUSEL"]
CarouselItemMediaType = Literal["IMAGE", "VIDEO"]
ContainerStatusState = Literal["EXPIRED", "ERROR", "FINISHED", "IN_PROGRESS", "PUBLISHED"]


class CarouselMediaItem(BaseModel):
    media_type: CarouselItemMediaType = Field(description="Media type for carousel item: IMAGE or VIDEO")
    url: str = Field(description="Publicly accessible URL of the media asset")


class ContainerStatus(BaseModel):
    id: str
    status: ContainerStatusState
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


class ThreadsPagingCursors(BaseModel):
    model_config = ConfigDict(extra="allow")

    before: str | None = Field(default=None, description="Cursor pointer for preceding page")
    after: str | None = Field(default=None, description="Cursor pointer for subsequent page")


class ThreadsPaging(BaseModel):
    model_config = ConfigDict(extra="allow")

    cursors: ThreadsPagingCursors | None = Field(default=None, description="Paging cursors")
    next: str | None = Field(default=None, description="Graph API endpoint URL for subsequent page")
    previous: str | None = Field(default=None, description="Graph API endpoint URL for preceding page")


class ThreadsPostPage(BaseModel):
    data: list[ThreadsPost] = Field(default_factory=list)
    paging: ThreadsPaging | None = None


class TokenInfo(BaseModel):
    access_token: str = Field(description="OAuth access token")
    token_type: str = Field(default="bearer", description="Token type, usually bearer")
    expires_in: int | None = Field(default=None, description="Expiration in seconds")
