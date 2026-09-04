from __future__ import annotations

from dataclasses import dataclass

from threads_client.config import DEFAULT_THREADS_API_HOST
from threads_client.exceptions import ThreadsAuthenticationError
from threads_client.transport import Transport


@dataclass
class ClientContext:
    """Shared state container for credentials and base configuration (Single Source of Truth)."""

    user_id: str = "me"
    access_token: str | None = None
    base_url: str = DEFAULT_THREADS_API_HOST


class BaseResource:
    """Base class for domain resources with URL routing and authentication validation."""

    def __init__(
        self,
        transport: Transport,
        context: ClientContext | None = None,
        *,
        base_url: str = DEFAULT_THREADS_API_HOST,
        access_token: str | None = None,
        user_id: str = "me",
    ) -> None:
        self._transport = transport
        self._context = context or ClientContext(
            user_id=user_id,
            access_token=access_token,
            base_url=base_url,
        )

    def _resolve_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        return f"{self._context.base_url.rstrip('/')}/{path_or_url.lstrip('/')}"

    def _require_access_token(self) -> str:
        if not self._context.access_token:
            raise ThreadsAuthenticationError("Access token is required for this operation.")
        return self._context.access_token

    def _get_extra_secrets(self) -> list[str]:
        return [self._context.access_token] if self._context.access_token else []

    @property
    def _user_id(self) -> str:
        return self._context.user_id
