"""Instagram Graph API read adapter (fixtures by default)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from app.adapters.base import (
    AccountProfile,
    Capabilities,
    CommentItem,
    MediaItem,
    Page,
    PlatformAdapter,
    PostItem,
    register_adapter,
)
from app.adapters.http import HttpClient
from app.config import get_settings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "instagram"


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _post_from_media(m: dict[str, Any], source: str) -> PostItem:
    return PostItem(
        source=source,
        external_id=str(m["id"]),
        permalink=m.get("permalink"),
        caption=m.get("caption"),
        posted_at=_parse_ts(m.get("timestamp")),
        media_type=m.get("media_type"),
        media=[MediaItem(url=m.get("media_url"), media_type=m.get("media_type"))],
        like_count=m.get("like_count"),
        comment_count=m.get("comments_count"),
        raw=m,
    )


def _comment_from_raw(c: dict[str, Any], source: str, post_external_id: str) -> CommentItem:
    return CommentItem(
        source=source,
        external_id=str(c["id"]),
        post_external_id=post_external_id,
        author_name=c.get("username"),
        body=c.get("text"),
        commented_at=_parse_ts(c.get("timestamp")),
        raw=c,
    )


class InstagramAdapter(PlatformAdapter):
    source = "instagram"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        ig_user_id: str | None = None,
        use_fixtures: bool | None = None,
    ) -> None:
        super().__init__(access_token=access_token)
        settings = get_settings()
        self.ig_user_id = ig_user_id
        self.use_fixtures = settings.use_fixtures if use_fixtures is None else use_fixtures
        self._http = HttpClient(base_url="https://graph.facebook.com/v21.0", access_token=access_token)

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

    def fetch_profile(self) -> AccountProfile:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("profile.json")
        else:
            data = self._http.get(
                f"/{self.ig_user_id}",
                params={"fields": "id,username,name,profile_picture_url,followers_count"},
            )
        assert isinstance(data, dict)
        return AccountProfile(
            source=self.source,
            external_id=str(data["id"]),
            display_name=data.get("name"),
            username=data.get("username"),
            avatar_url=data.get("profile_picture_url"),
            follower_count=data.get("followers_count"),
            profile_url=f"https://instagram.com/{data.get('username')}" if data.get("username") else None,
        )

    def iter_posts(self, *, cursor: str | None = None) -> Iterator[Page]:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("media.json")
            assert isinstance(data, dict)
            items = [_post_from_media(m, self.source) for m in (data.get("data") or [])]
            yield Page(items=items, cursor=None, has_more=False)
            return

        page_cursor = cursor
        while True:
            params: dict[str, Any] = {
                "fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count",
                "limit": 50,
            }
            if page_cursor:
                params["after"] = page_cursor
            data = self._http.get(f"/{self.ig_user_id}/media", params=params)
            assert isinstance(data, dict)
            items = [_post_from_media(m, self.source) for m in (data.get("data") or [])]
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
            data = self._load("comments.json")
            assert isinstance(data, dict)
            items = [
                _comment_from_raw(c, self.source, post_external_id)
                for c in (data.get("data") or [])
                if str(c.get("media_id", post_external_id)) == post_external_id or "media_id" not in c
            ]
            yield Page(items=items, cursor=None, has_more=False)
            return

        page_cursor = cursor
        while True:
            params: dict[str, Any] = {"fields": "id,text,username,timestamp", "limit": 50}
            if page_cursor:
                params["after"] = page_cursor
            data = self._http.get(f"/{post_external_id}/comments", params=params)
            assert isinstance(data, dict)
            items = [
                _comment_from_raw(c, self.source, post_external_id)
                for c in (data.get("data") or [])
                if str(c.get("media_id", post_external_id)) == post_external_id or "media_id" not in c
            ]
            paging = (data.get("paging") or {}).get("cursors") or {}
            next_cursor = paging.get("after")
            has_more = bool(next_cursor)
            yield Page(items=items, cursor=next_cursor, has_more=has_more)
            if not has_more:
                break
            page_cursor = next_cursor


register_adapter("instagram", InstagramAdapter)
