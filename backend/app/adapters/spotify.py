"""Spotify Web API read client (fixtures by default)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from app.adapters.base import (
    AdapterError,
    ArtistProfile,
    Capabilities,
    CredentialError,
    Page,
    PlatformAdapter,
    ReleaseItem,
    TrackItem,
    register_adapter,
)
from app.adapters.http import HttpClient
from app.config import get_settings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "spotify"


class SpotifyAdapter(PlatformAdapter):
    source = "spotify"

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
        self._http = HttpClient(base_url="https://api.spotify.com/v1", access_token=access_token)

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(can_read_profile=True, can_read_catalog=True)

    def _require_live_token(self) -> None:
        if self.use_fixtures:
            return
        if not self.access_token:
            self.authenticate()
        if not self.access_token:
            raise CredentialError(
                f"{self.source}: live sync requires Spotify credentials "
                "(set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env)"
            )

    def authenticate(self) -> None:
        """Obtain a client-credentials token for public catalog reads."""
        if self.use_fixtures or self.access_token:
            return
        settings = get_settings()
        if not settings.spotify_client_id or not settings.spotify_client_secret:
            return
        try:
            response = httpx.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=(settings.spotify_client_id, settings.spotify_client_secret),
                headers={"User-Agent": settings.user_agent},
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            raise AdapterError(f"Spotify token request failed: {exc}") from exc
        if response.status_code >= 400:
            raise AdapterError(f"Spotify token request failed: HTTP {response.status_code}")
        data = response.json()
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise AdapterError("Spotify token response missing access_token")
        self.access_token = token
        self._http.access_token = token

    def _load(self, name: str) -> Any:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def fetch_profile(self) -> ArtistProfile:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("artist.json")
        else:
            self._require_live_artist_id()
            data = self._http.get(f"/artists/{self.artist_id}")
        assert isinstance(data, dict)
        images = data.get("images") or []
        related = []
        if self.use_fixtures:
            related_data = self._load("related.json")
            related = [a["name"] for a in related_data.get("artists", [])]
        return ArtistProfile(
            source=self.source,
            external_id=str(data["id"]),
            name=data["name"],
            genres=list(data.get("genres") or []),
            image_url=images[0]["url"] if images else None,
            follower_count=(data.get("followers") or {}).get("total"),
            related_artists=related,
            meta={"popularity": data.get("popularity")},
        )

    def search_identity(self, query: str) -> list[ArtistProfile]:
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("search.json")
        else:
            data = self._http.get("/search", params={"q": query, "type": "artist", "limit": 5})
        assert isinstance(data, dict)
        artists = (data.get("artists") or {}).get("items") or []
        results: list[ArtistProfile] = []
        for a in artists:
            images = a.get("images") or []
            results.append(
                ArtistProfile(
                    source=self.source,
                    external_id=str(a["id"]),
                    name=a["name"],
                    genres=list(a.get("genres") or []),
                    image_url=images[0]["url"] if images else None,
                    follower_count=(a.get("followers") or {}).get("total"),
                )
            )
        return results

    def iter_catalog(self, *, cursor: str | None = None) -> Iterator[Page]:
        # Spotify capped Get Artist's Albums max limit at 10 (was 50).
        page_limit = 10
        self._require_live_token()
        if self.use_fixtures:
            data = self._load("albums.json")
            items_raw = data.get("items") or []
            yield Page(items=self._releases_from_albums(items_raw), cursor=None, has_more=False)
            return

        self._require_live_artist_id()
        aid = self.artist_id
        offset = int(cursor or 0)
        while True:
            data = self._http.get(
                f"/artists/{aid}/albums",
                params={
                    "include_groups": "album,single",
                    "limit": page_limit,
                    "offset": offset,
                },
            )
            assert isinstance(data, dict)
            items_raw = data.get("items") or []
            total = int(data.get("total") or 0)
            next_offset = offset + len(items_raw)
            has_more = bool(data.get("next")) or (len(items_raw) > 0 and next_offset < total)
            yield Page(
                items=self._releases_from_albums(items_raw),
                cursor=str(next_offset) if has_more else None,
                has_more=has_more,
            )
            if not has_more:
                break
            offset = next_offset

    def _releases_from_albums(self, items_raw: list[Any]) -> list[ReleaseItem]:
        releases: list[ReleaseItem] = []
        for alb in items_raw:
            tracks: list[TrackItem] = []
            if self.use_fixtures:
                tracks_data = self._load("tracks.json")
                for t in tracks_data.get("items") or []:
                    if t.get("album_id") == alb["id"] or not t.get("album_id"):
                        tracks.append(
                            TrackItem(
                                source=self.source,
                                external_id=str(t["id"]),
                                title=t["name"],
                                duration_ms=t.get("duration_ms"),
                                track_number=t.get("track_number"),
                            )
                        )
            releases.append(
                ReleaseItem(
                    source=self.source,
                    external_id=str(alb["id"]),
                    title=alb["name"],
                    release_date=alb.get("release_date"),
                    album_type=alb.get("album_type"),
                    cover_url=(alb.get("images") or [{}])[0].get("url"),
                    tracks=tracks,
                )
            )
        return releases


register_adapter("spotify", SpotifyAdapter)
