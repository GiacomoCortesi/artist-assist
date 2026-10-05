"""SoundCloud API read client (fixtures by default)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.adapters.base import (
    ArtistProfile,
    Capabilities,
    Page,
    PlatformAdapter,
    ReleaseItem,
    TrackItem,
    register_adapter,
)
from app.adapters.http import HttpClient
from app.config import get_settings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "soundcloud"


class SoundCloudAdapter(PlatformAdapter):
    source = "soundcloud"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        user_id: str | None = None,
        use_fixtures: bool | None = None,
    ) -> None:
        super().__init__(access_token=access_token)
        settings = get_settings()
        self.user_id = user_id
        self.use_fixtures = settings.use_fixtures if use_fixtures is None else use_fixtures
        self._http = HttpClient(base_url="https://api.soundcloud.com", access_token=access_token)

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(can_read_profile=True, can_read_catalog=True)

    def _load(self, name: str) -> Any:
        path = FIXTURES / name
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def fetch_profile(self) -> ArtistProfile:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("user.json")
            if not data:
                return ArtistProfile(source=self.source, external_id="", name="", meta={"no_data": True})
        else:
            data = self._http.get("/me")
        assert isinstance(data, dict)
        return ArtistProfile(
            source=self.source,
            external_id=str(data.get("id", "")),
            name=data.get("username") or data.get("full_name") or "",
            image_url=data.get("avatar_url"),
            follower_count=data.get("followers_count"),
            meta={"track_count": data.get("track_count"), "playlist_count": data.get("playlist_count")},
        )

    def search_identity(self, query: str) -> list[ArtistProfile]:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("search.json")
            users = data.get("collection") or []
        else:
            data = self._http.get("/users", params={"q": query, "limit": 5})
            users = data if isinstance(data, list) else []
        return [
            ArtistProfile(
                source=self.source,
                external_id=str(u["id"]),
                name=u.get("username") or "",
                image_url=u.get("avatar_url"),
                follower_count=u.get("followers_count"),
            )
            for u in users
        ]

    def iter_catalog(self, *, cursor: str | None = None) -> Iterator[Page]:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("tracks.json")
            tracks_raw = data.get("collection") or []
        else:
            uid = self.user_id or "me"
            data = self._http.get(f"/users/{uid}/tracks", params={"limit": 50})
            tracks_raw = data if isinstance(data, list) else (data.get("collection") or [])

        if not tracks_raw:
            yield Page(items=[], cursor=None, has_more=False)
            return

        tracks = [
            TrackItem(
                source=self.source,
                external_id=str(t["id"]),
                title=t.get("title") or "Untitled",
                duration_ms=t.get("duration"),
                play_count=t.get("playback_count"),
            )
            for t in tracks_raw
        ]
        # SoundCloud tracks as a synthetic "uploads" release for merge
        release = ReleaseItem(
            source=self.source,
            external_id=f"sc-uploads-{self.user_id or 'me'}",
            title="SoundCloud Uploads",
            release_date=None,
            album_type="compilation",
            tracks=tracks,
        )
        yield Page(items=[release], cursor=None, has_more=False)


register_adapter("soundcloud", SoundCloudAdapter)
