"""Threads API read adapter with long-lived token refresh hook."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.adapters.base import (
    AccountProfile,
    Capabilities,
    CommentItem,
    Page,
    PlatformAdapter,
    PostItem,
    register_adapter,
)
from app.adapters.http import HttpClient
from app.config import get_settings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "threads"


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _post_from_raw(t: dict[str, Any], source: str) -> PostItem:
    return PostItem(
        source=source,
        external_id=str(t["id"]),
        permalink=t.get("permalink"),
        caption=t.get("text"),
        posted_at=_parse_ts(t.get("timestamp")),
        raw=t,
    )


def _comment_from_raw(r: dict[str, Any], source: str, post_external_id: str) -> CommentItem:
    return CommentItem(
        source=source,
        external_id=str(r["id"]),
        post_external_id=post_external_id,
        author_name=r.get("username"),
        body=r.get("text"),
        commented_at=_parse_ts(r.get("timestamp")),
        raw=r,
    )


class ThreadsAdapter(PlatformAdapter):
    source = "threads"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        user_id: str | None = None,
        token_expires_at: datetime | None = None,
        use_fixtures: bool | None = None,
    ) -> None:
        super().__init__(access_token=access_token)
        settings = get_settings()
        self.user_id = user_id
        self.token_expires_at = token_expires_at
        self.use_fixtures = settings.use_fixtures if use_fixtures is None else use_fixtures
        self._http = HttpClient(base_url="https://graph.threads.net/v1.0", access_token=access_token)
        self.caveats = {
            "insights_before_2024_06_01": False,
            "top_level_replies_only": True,
        }

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            can_read_profile=True,
            can_read_posts=True,
            can_read_comments=True,
            can_read_insights=True,
        )

    def _load(self, name: str) -> Any:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def needs_refresh(self, *, within_days: int = 7) -> bool:
        if not self.token_expires_at:
            return False
        return self.token_expires_at <= datetime.now(timezone.utc) + timedelta(days=within_days)

    def refresh_auth(self) -> str | None:
        """Refresh long-lived Threads token before ~60-day expiry."""
        if self.use_fixtures:
            self.access_token = "refreshed-threads-token"
            self.token_expires_at = datetime.now(timezone.utc) + timedelta(days=60)
            return self.access_token
        self._require_live_token()
        data = self._http.get(
            "/refresh_access_token",
            params={"grant_type": "th_refresh_token", "access_token": self.access_token},
            auth_header=False,
        )
        assert isinstance(data, dict)
        self.access_token = str(data["access_token"])
        expires_in = int(data.get("expires_in") or 60 * 24 * 3600)
        self.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return self.access_token

    def fetch_profile(self) -> AccountProfile:
        if self.needs_refresh():
            self.refresh_auth()
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("profile.json")
        else:
            data = self._http.get(
                "/me",
                params={"fields": "id,username,name,threads_profile_picture_url"},
            )
        assert isinstance(data, dict)
        return AccountProfile(
            source=self.source,
            external_id=str(data["id"]),
            display_name=data.get("name"),
            username=data.get("username"),
            avatar_url=data.get("threads_profile_picture_url"),
            meta={"caveats": self.caveats},
        )

    def iter_posts(self, *, cursor: str | None = None) -> Iterator[Page]:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("threads.json")
            assert isinstance(data, dict)
            items = [_post_from_raw(t, self.source) for t in (data.get("data") or [])]
            yield Page(items=items, cursor=None, has_more=False)
            return

        page_cursor = cursor
        while True:
            params: dict[str, Any] = {"fields": "id,text,timestamp,permalink", "limit": 50}
            if page_cursor:
                params["after"] = page_cursor
            data = self._http.get(f"/{self.user_id}/threads", params=params)
            assert isinstance(data, dict)
            items = [_post_from_raw(t, self.source) for t in (data.get("data") or [])]
            paging = (data.get("paging") or {}).get("cursors") or {}
            next_cursor = paging.get("after")
            has_more = bool(next_cursor)
            yield Page(items=items, cursor=next_cursor, has_more=has_more)
            if not has_more:
                break
            page_cursor = next_cursor

    def iter_comments(self, post_external_id: str, *, cursor: str | None = None) -> Iterator[Page]:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("replies.json")
            assert isinstance(data, dict)
            items = [
                _comment_from_raw(r, self.source, post_external_id) for r in (data.get("data") or [])
            ]
            yield Page(items=items, cursor=None, has_more=False)
            return

        page_cursor = cursor
        while True:
            params: dict[str, Any] = {"fields": "id,text,username,timestamp", "limit": 50}
            if page_cursor:
                params["after"] = page_cursor
            data = self._http.get(f"/{post_external_id}/replies", params=params)
            assert isinstance(data, dict)
            items = [
                _comment_from_raw(r, self.source, post_external_id) for r in (data.get("data") or [])
            ]
            paging = (data.get("paging") or {}).get("cursors") or {}
            next_cursor = paging.get("after")
            has_more = bool(next_cursor)
            yield Page(items=items, cursor=next_cursor, has_more=has_more)
            if not has_more:
                break
            page_cursor = next_cursor


register_adapter("threads", ThreadsAdapter)
