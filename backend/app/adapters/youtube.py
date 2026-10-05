"""YouTube Data + Analytics read adapter."""

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

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "youtube"


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _post_from_search_item(v: dict[str, Any], source: str) -> PostItem:
    snippet = v.get("snippet") or {}
    vid = v.get("id") or {}
    video_id = vid.get("videoId") if isinstance(vid, dict) else v.get("id")
    duration_hint = (v.get("contentDetails") or {}).get("duration") or ""
    is_short = "short" in (snippet.get("title") or "").casefold() or (
        "PT" in duration_hint and "M" not in duration_hint
    )
    stats = v.get("statistics") or {}
    return PostItem(
        source=source,
        external_id=str(video_id),
        permalink=f"https://youtube.com/watch?v={video_id}",
        caption=snippet.get("title"),
        posted_at=_parse_ts(snippet.get("publishedAt")),
        media_type="short" if is_short else "video",
        media=[
            MediaItem(
                url=f"https://youtube.com/watch?v={video_id}",
                media_type="video",
                thumbnail_url=((snippet.get("thumbnails") or {}).get("medium") or {}).get("url"),
            )
        ],
        view_count=int(stats["viewCount"]) if stats.get("viewCount") else None,
        like_count=int(stats["likeCount"]) if stats.get("likeCount") else None,
        comment_count=int(stats["commentCount"]) if stats.get("commentCount") else None,
        raw={**v, "format": "short" if is_short else "long"},
    )


def _comment_from_thread(
    thread: dict[str, Any], source: str, post_external_id: str
) -> CommentItem:
    top = ((thread.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
    return CommentItem(
        source=source,
        external_id=str(thread.get("id")),
        post_external_id=post_external_id,
        author_name=top.get("authorDisplayName"),
        body=top.get("textDisplay"),
        commented_at=_parse_ts(top.get("publishedAt")),
        raw=thread,
    )


class YouTubeAdapter(PlatformAdapter):
    source = "youtube"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        channel_id: str | None = None,
        use_fixtures: bool | None = None,
        quota_used: int = 0,
        quota_limit: int = 10000,
    ) -> None:
        super().__init__(access_token=access_token)
        settings = get_settings()
        self.channel_id = channel_id
        self.use_fixtures = settings.use_fixtures if use_fixtures is None else use_fixtures
        self.quota_used = quota_used
        self.quota_limit = quota_limit
        self._http = HttpClient(base_url="https://www.googleapis.com/youtube/v3", access_token=access_token)
        self._analytics = HttpClient(
            base_url="https://youtubeanalytics.googleapis.com/v2", access_token=access_token
        )

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

    def quota_status(self) -> dict[str, int]:
        return {
            "used": self.quota_used,
            "limit": self.quota_limit,
            "remaining": max(0, self.quota_limit - self.quota_used),
        }

    def fetch_profile(self) -> AccountProfile:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("channel.json")
        else:
            data = self._http.get(
                "/channels",
                params={"part": "snippet,statistics", "mine": "true"},
            )
        assert isinstance(data, dict)
        item = (data.get("items") or [{}])[0]
        snippet = item.get("snippet") or {}
        stats = item.get("statistics") or {}
        self.quota_used += 1
        return AccountProfile(
            source=self.source,
            external_id=str(item.get("id") or self.channel_id or ""),
            display_name=snippet.get("title"),
            avatar_url=((snippet.get("thumbnails") or {}).get("default") or {}).get("url"),
            follower_count=int(stats["subscriberCount"]) if stats.get("subscriberCount") else None,
            profile_url=f"https://youtube.com/channel/{item.get('id')}" if item.get("id") else None,
            meta={"quota": self.quota_status(), "video_count": stats.get("videoCount")},
        )

    def iter_posts(self, *, cursor: str | None = None) -> Iterator[Page]:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("videos.json")
            assert isinstance(data, dict)
            self.quota_used += 100
            items = [_post_from_search_item(v, self.source) for v in (data.get("items") or [])]
            yield Page(items=items, cursor=None, has_more=False)
            return

        page_token = cursor
        while True:
            params: dict[str, Any] = {
                "part": "snippet",
                "forMine": "true",
                "type": "video",
                "maxResults": 25,
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._http.get("/search", params=params)
            assert isinstance(data, dict)
            self.quota_used += 100
            items = [_post_from_search_item(v, self.source) for v in (data.get("items") or [])]
            next_token = data.get("nextPageToken")
            has_more = bool(next_token)
            yield Page(items=items, cursor=next_token, has_more=has_more)
            if not has_more:
                break
            page_token = next_token

    def iter_comments(self, post_external_id: str, *, cursor: str | None = None) -> Iterator[Page]:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("comments.json")
            assert isinstance(data, dict)
            self.quota_used += 1
            items = [
                _comment_from_thread(thread, self.source, post_external_id)
                for thread in (data.get("items") or [])
            ]
            yield Page(items=items, cursor=None, has_more=False)
            return

        page_token = cursor
        while True:
            params: dict[str, Any] = {
                "part": "snippet",
                "videoId": post_external_id,
                "maxResults": 50,
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._http.get("/commentThreads", params=params)
            assert isinstance(data, dict)
            self.quota_used += 1
            items = [
                _comment_from_thread(thread, self.source, post_external_id)
                for thread in (data.get("items") or [])
            ]
            next_token = data.get("nextPageToken")
            has_more = bool(next_token)
            yield Page(items=items, cursor=next_token, has_more=has_more)
            if not has_more:
                break
            page_token = next_token

    def fetch_analytics_daily(self) -> list[dict[str, Any]]:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("analytics.json")
        else:
            data = self._analytics.get(
                "/reports",
                params={
                    "ids": "channel==MINE",
                    "metrics": "views,estimatedMinutesWatched,subscribersGained,subscribersLost",
                    "dimensions": "day",
                    "startDate": "2024-01-01",
                    "endDate": "2024-12-31",
                },
            )
        assert isinstance(data, dict)
        rows = []
        headers = data.get("columnHeaders") or []
        names = [h.get("name") for h in headers]
        for row in data.get("rows") or []:
            rows.append(dict(zip(names, row, strict=False)))
        return rows


register_adapter("youtube", YouTubeAdapter)
