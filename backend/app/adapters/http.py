"""Shared HTTP client helpers for platform adapters."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.adapters.base import AdapterError, AuthError, NotFoundError, RateLimitError
from app.config import get_settings
from app.security.tokens import redact_secrets

logger = logging.getLogger(__name__)


class HttpClient:
    def __init__(self, *, base_url: str = "", access_token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        settings = get_settings()
        self._client = httpx.Client(
            timeout=30.0,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        auth_header: bool = True,
    ) -> dict[str, Any] | list[Any]:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        hdrs = dict(headers or {})
        if auth_header and self.access_token:
            hdrs.setdefault("Authorization", f"Bearer {self.access_token}")
        try:
            response = self._client.request(method, url, params=params, json=json, headers=hdrs)
        except httpx.HTTPError as exc:
            raise AdapterError(f"HTTP transport error: {exc}") from exc

        if response.status_code == 401:
            raise AuthError("Unauthorized")
        if response.status_code == 404:
            raise NotFoundError("Not found")
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                "Rate limited",
                retry_after=float(retry_after) if retry_after else None,
            )
        if response.status_code >= 400:
            body = redact_secrets(response.text, [self.access_token or ""]).strip()
            logger.error(
                "Platform HTTP %s %s → %s: %s",
                method,
                url,
                response.status_code,
                body[:500],
            )
            detail = body[:300] if body else f"HTTP {response.status_code}"
            raise AdapterError(detail)

        if not response.content:
            return {}
        return response.json()

    def get(self, path: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        return self.request("GET", path, **kwargs)
