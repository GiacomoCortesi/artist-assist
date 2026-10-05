"""Deezer public API read client (fixtures by default)."""

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

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "deezer"


class DeezerAdapter(PlatformAdapter):
    source = "deezer"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        artist_id: str | None = None,
        use_fixtures: bool | None = None,
    ) -> None:
        super().__init__(access_token=access_token)
        settings = get_settings()
        self.artist_id = artist_id
        self.use_fixtures = settings.use_fixtures if use_fixtures is None else use_fixtures
        self._http = HttpClient(base_url="https://api.deezer.com", access_token=access_token)

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(can_read_profile=True, can_read_catalog=True)

    def _load(self, name: str) -> Any:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def fetch_profile(self) -> ArtistProfile:
        self._require_live_artist_id()
        if self.use_fixtures:
            data = self._load("artist.json")
        else:
            data = self._http.get(f"/artist/{self.artist_id}", auth_header=False)
        assert isinstance(data, dict)
        return ArtistProfile(
            source=self.source,
            external_id=str(data["id"]),
            name=data["name"],
            image_url=data.get("picture_medium") or data.get("picture"),
            follower_count=data.get("nb_fan"),
            meta={"nb_album": data.get("nb_album")},
        )

    def search_identity(self, query: str) -> list[ArtistProfile]:
        if self.use_fixtures:
            data = self._load("search.json")
        else:
            data = self._http.get("/search/artist", params={"q": query}, auth_header=False)
        assert isinstance(data, dict)
        return [
            ArtistProfile(
                source=self.source,
                external_id=str(a["id"]),
                name=a["name"],
                image_url=a.get("picture_medium"),
                follower_count=a.get("nb_fan"),
            )
            for a in (data.get("data") or [])
        ]

    def iter_catalog(self, *, cursor: str | None = None) -> Iterator[Page]:
        self._require_live_artist_id()
        if self.use_fixtures:
            data = self._load("albums.json")
            albums = data.get("data") or []
        else:
            data = self._http.get(f"/artist/{self.artist_id}/albums", auth_header=False)
            assert isinstance(data, dict)
            albums = data.get("data") or []

        releases: list[ReleaseItem] = []
        for alb in albums:
            tracks: list[TrackItem] = []
            if self.use_fixtures:
                tracks_data = self._load("tracks.json")
                for t in tracks_data.get("data") or []:
                    if str(t.get("album_id")) == str(alb["id"]) or not t.get("album_id"):
                        tracks.append(
                            TrackItem(
                                source=self.source,
                                external_id=str(t["id"]),
                                title=t["title"],
                                duration_ms=(t.get("duration") or 0) * 1000,
                            )
                        )
            releases.append(
                ReleaseItem(
                    source=self.source,
                    external_id=str(alb["id"]),
                    title=alb["title"],
                    release_date=alb.get("release_date"),
                    cover_url=alb.get("cover_medium"),
                    tracks=tracks,
                )
            )
        yield Page(items=releases, cursor=None, has_more=False)


register_adapter("deezer", DeezerAdapter)
