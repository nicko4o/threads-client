from __future__ import annotations

from threads_client.models import TokenInfo
from threads_client.resources.base import BaseResource
from threads_client.transport import QueryParamsMapping


class TokensResource(BaseResource):
    """Resource managing OAuth tokens exchange and renewal."""

    async def exchange(self, short_token: str, app_secret: str) -> TokenInfo:
        url = self._resolve_url("access_token")
        params: QueryParamsMapping = {
            "grant_type": "th_exchange_token",
            "client_secret": app_secret,
            "access_token": short_token,
        }
        resp = await self._transport.request(
            "GET",
            url,
            params=params,
            extra_secrets=[short_token, app_secret],
        )
        return TokenInfo.model_validate(resp.json())

    async def refresh(self, long_token: str) -> TokenInfo:
        url = self._resolve_url("refresh_access_token")
        params: QueryParamsMapping = {
            "grant_type": "th_refresh_token",
            "access_token": long_token,
        }
        resp = await self._transport.request(
            "GET",
            url,
            params=params,
            extra_secrets=[long_token],
        )
        return TokenInfo.model_validate(resp.json())
