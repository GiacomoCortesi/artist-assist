"""TikTok Display API read adapter (no comments/reach)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from app.adapters.base import (
    AccountProfile,
    Capabilities,
    MediaItem,
    Page,
    PlatformAdapter,
    PostItem,
    register_adapter,
)
from app.adapters.http import HttpClient
from app.config import get_settings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tiktok"


def _parse_ts(value: int | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, int):
        return datetime.utcfromtimestamp(value)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _post_from_video(v: dict[str, Any], source: str) -> PostItem:
    return PostItem(
        source=source,
        external_id=str(v["id"]),
        caption=v.get("video_description") or v.get("title"),
        posted_at=_parse_ts(v.get("create_time")),
        media_type="video",
        media=[
            MediaItem(
                url=v.get("share_url"),
                media_type="video",
                thumbnail_url=v.get("cover_image_url"),
            )
        ],
        like_count=v.get("like_count"),
        comment_count=v.get("comment_count"),
        view_count=v.get("view_count"),
        raw=v,
    )


class TikTokAdapter(PlatformAdapter):
    source = "tiktok"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        use_fixtures: bool | None = None,
    ) -> None:
        super().__init__(access_token=access_token)
        settings = get_settings()
        self.use_fixtures = settings.use_fixtures if use_fixtures is None else use_fixtures
        self._http = HttpClient(base_url="https://open.tiktokapis.com/v2", access_token=access_token)

    @property
    def capabilities(self) -> Capabilities:
        # TikTok Display: profile + videos; no comments / reach
        return Capabilities(
            can_read_profile=True,
            can_read_posts=True,
            can_read_comments=False,
            can_read_insights=False,
        )

    def _load(self, name: str) -> Any:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def fetch_profile(self) -> AccountProfile:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("user.json")
        else:
            data = self._http.get(
                "/user/info/",
                params={"fields": "open_id,union_id,avatar_url,display_name,follower_count,video_count"},
            )
        assert isinstance(data, dict)
        user = data.get("data", data).get("user", data.get("data", data))
        if "user" in (data.get("data") or {}):
            user = data["data"]["user"]
        return AccountProfile(
            source=self.source,
            external_id=str(user.get("open_id") or user.get("id")),
            display_name=user.get("display_name"),
            avatar_url=user.get("avatar_url"),
            follower_count=user.get("follower_count"),
            meta={"video_count": user.get("video_count"), "scopes": ["user.info.basic", "user.info.stats", "video.list"]},
        )

    def iter_posts(self, *, cursor: str | None = None) -> Iterator[Page]:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("videos.json")
            assert isinstance(data, dict)
            videos = (data.get("data") or {}).get("videos") or data.get("videos") or []
            items = [_post_from_video(v, self.source) for v in videos]
            yield Page(items=items, cursor=None, has_more=False)
            return

        page_cursor = int(cursor or 0)
        while True:
            data = self._http.request(
                "POST",
                "/video/list/",
                json={"max_count": 20, "cursor": page_cursor},
            )
            assert isinstance(data, dict)
            payload = data.get("data") or {}
            videos = payload.get("videos") or data.get("videos") or []
            items = [_post_from_video(v, self.source) for v in videos]
            has_more = bool(payload.get("has_more"))
            next_cursor = payload.get("cursor")
            next_cursor_str = str(next_cursor) if next_cursor is not None and has_more else None
            yield Page(items=items, cursor=next_cursor_str, has_more=has_more)
            if not has_more or next_cursor is None:
                break
            page_cursor = int(next_cursor)


register_adapter("tiktok", TikTokAdapter)
