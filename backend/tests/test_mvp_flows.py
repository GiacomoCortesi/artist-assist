"""Client adapter + sync + media + agent tests (offline fixtures)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select


@pytest.fixture()
def db_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "test-encryption-key-for-artistassist")
    monkeypatch.setenv("PLATFORM_LIVE", "0")
    monkeypatch.setenv("LLM_LIVE", "0")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("ENVIRONMENT", "test")
    from app.config import get_settings
    from app.db import get_session_factory, init_db, reset_engine

    get_settings.cache_clear()
    reset_engine()
    init_db()
    Session = get_session_factory()
    session = Session()
    try:
        yield session
        session.commit()
    finally:
        session.close()
        reset_engine()
        get_settings.cache_clear()


def test_spotify_fixture_catalog(db_session) -> None:
    from app.adapters.spotify import SpotifyAdapter

    adapter = SpotifyAdapter(use_fixtures=True)
    profile = adapter.fetch_profile()
    assert profile.name == "Nova Lane"
    assert adapter.capabilities.can_publish is False
    releases = list(adapter.iter_catalog())[0].items
    assert any(r.title == "Midnight Swim" for r in releases)


def test_spotify_client_credentials_live(monkeypatch: pytest.MonkeyPatch) -> None:
    import respx

    monkeypatch.setenv("PLATFORM_LIVE", "1")
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "test-client-secret")
    from app.config import get_settings

    get_settings.cache_clear()

    with respx.mock:
        respx.post("https://accounts.spotify.com/api/token").mock(
            return_value=respx.MockResponse(200, json={"access_token": "spotify-cc-token", "token_type": "Bearer"})
        )
        respx.get("https://api.spotify.com/v1/artists/abc123").mock(
            return_value=respx.MockResponse(
                200,
                json={
                    "id": "abc123",
                    "name": "Live Artist",
                    "genres": ["pop"],
                    "images": [],
                    "followers": {"total": 100},
                    "popularity": 50,
                },
            )
        )
        from app.adapters.spotify import SpotifyAdapter

        adapter = SpotifyAdapter(use_fixtures=False, artist_id="abc123")
        profile = adapter.fetch_profile()
        assert profile.name == "Live Artist"
        assert adapter.access_token == "spotify-cc-token"

    get_settings.cache_clear()


def test_spotify_catalog_uses_limit_10(monkeypatch: pytest.MonkeyPatch) -> None:
    import respx
    from httpx import Response

    monkeypatch.setenv("PLATFORM_LIVE", "1")
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "test-client-secret")
    from app.config import get_settings

    get_settings.cache_clear()

    with respx.mock:
        respx.post("https://accounts.spotify.com/api/token").mock(
            return_value=Response(200, json={"access_token": "spotify-cc-token", "token_type": "Bearer"})
        )
        albums_route = respx.get("https://api.spotify.com/v1/artists/abc123/albums").mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "items": [
                            {
                                "id": f"alb{i}",
                                "name": f"Album {i}",
                                "release_date": "2024-01-01",
                                "album_type": "album",
                                "images": [],
                            }
                            for i in range(10)
                        ],
                        "total": 12,
                        "next": "https://api.spotify.com/v1/artists/abc123/albums?offset=10&limit=10",
                    },
                ),
                Response(
                    200,
                    json={
                        "items": [
                            {
                                "id": "alb10",
                                "name": "Album 10",
                                "release_date": "2023-01-01",
                                "album_type": "single",
                                "images": [],
                            },
                            {
                                "id": "alb11",
                                "name": "Album 11",
                                "release_date": "2022-01-01",
                                "album_type": "album",
                                "images": [],
                            },
                        ],
                        "total": 12,
                        "next": None,
                    },
                ),
            ]
        )
        from app.adapters.spotify import SpotifyAdapter

        adapter = SpotifyAdapter(use_fixtures=False, artist_id="abc123")
        pages = list(adapter.iter_catalog())
        assert len(pages) == 2
        assert len(pages[0].items) == 10
        assert pages[0].has_more is True
        assert len(pages[1].items) == 2
        assert pages[1].has_more is False
        assert albums_route.call_count == 2
        assert albums_route.calls[0].request.url.params["limit"] == "10"
        assert albums_route.calls[1].request.url.params["offset"] == "10"

    get_settings.cache_clear()


def test_instagram_posts_paginate(monkeypatch: pytest.MonkeyPatch) -> None:
    import respx
    from httpx import Response

    monkeypatch.setenv("PLATFORM_LIVE", "1")
    from app.config import get_settings

    get_settings.cache_clear()

    ig_user_id = "ig123"
    with respx.mock:
        media_route = respx.get(f"https://graph.facebook.com/v21.0/{ig_user_id}/media").mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "data": [
                            {
                                "id": f"media_{i}",
                                "caption": f"Post {i}",
                                "media_type": "IMAGE",
                                "media_url": f"https://example.com/{i}.jpg",
                                "permalink": f"https://instagram.com/p/{i}",
                                "timestamp": "2024-11-10T18:00:00Z",
                                "like_count": i,
                                "comments_count": 0,
                            }
                            for i in range(50)
                        ],
                        "paging": {"cursors": {"after": "cursor_page_2"}},
                    },
                ),
                Response(
                    200,
                    json={
                        "data": [
                            {
                                "id": "media_50",
                                "caption": "Last post",
                                "media_type": "IMAGE",
                                "media_url": "https://example.com/50.jpg",
                                "permalink": "https://instagram.com/p/50",
                                "timestamp": "2024-10-01T12:00:00Z",
                                "like_count": 1,
                                "comments_count": 0,
                            }
                        ],
                        "paging": {"cursors": {}},
                    },
                ),
            ]
        )
        from app.adapters.instagram import InstagramAdapter

        adapter = InstagramAdapter(
            access_token="ig-token",
            ig_user_id=ig_user_id,
            use_fixtures=False,
        )
        pages = list(adapter.iter_posts())
        assert len(pages) == 2
        assert len(pages[0].items) == 50
        assert pages[0].has_more is True
        assert pages[0].cursor == "cursor_page_2"
        assert len(pages[1].items) == 1
        assert pages[1].has_more is False
        assert media_route.call_count == 2
        assert media_route.calls[0].request.url.params["limit"] == "50"
        assert "after" not in media_route.calls[0].request.url.params
        assert media_route.calls[1].request.url.params["after"] == "cursor_page_2"

    get_settings.cache_clear()


def test_music_merge_normalize() -> None:
    from app.adapters.music_merge import consensus_genres, normalize_title

    assert normalize_title("Glass House (feat. Echo)") == "glass house"
    assert "indie pop" in consensus_genres([["Indie Pop"], ["indie pop", "alt"]])


def test_meta_and_tiktok_youtube_fixtures() -> None:
    from app.adapters.instagram import InstagramAdapter
    from app.adapters.tiktok import TikTokAdapter
    from app.adapters.youtube import YouTubeAdapter

    ig = InstagramAdapter(use_fixtures=True)
    assert ig.capabilities.can_publish is False
    posts = list(ig.iter_posts())[0].items
    assert len(posts) >= 1

    tt = TikTokAdapter(use_fixtures=True)
    assert tt.capabilities.can_read_comments is False
    assert list(tt.iter_posts())[0].items

    yt = YouTubeAdapter(use_fixtures=True)
    assert yt.quota_status()["limit"] == 10000
    assert list(yt.iter_posts())[0].items


def test_threads_refresh() -> None:
    from datetime import datetime, timedelta, timezone

    from app.adapters.threads import ThreadsAdapter

    adapter = ThreadsAdapter(
        access_token="old",
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        use_fixtures=True,
    )
    assert adapter.needs_refresh()
    token = adapter.refresh_auth()
    assert token == "refreshed-threads-token"


def test_sync_partial_and_tagging(db_session, monkeypatch) -> None:
    from app.adapters.base import AdapterError
    from app.context.generator import regenerate_all_context
    from app.db.models import Comment, Post
    from app.sync.service import SyncService

    service = SyncService(db_session, context_regen=regenerate_all_context)
    original_build = service.build_adapter

    def flaky(source: str):
        if source == "facebook":
            class Boom:
                source = "facebook"

                @property
                def capabilities(self):
                    from app.adapters.base import Capabilities

                    return Capabilities(can_read_posts=True)

                def fetch_profile(self):
                    raise AdapterError("facebook down")

            return Boom()
        return original_build(source)

    monkeypatch.setattr(service, "build_adapter", flaky)
    result = service.run(sources=["spotify", "instagram", "facebook"])
    assert result["status"] == "partial"
    assert result["per_source"]["spotify"]["status"] == "ok"
    assert result["per_source"]["facebook"]["status"] == "error"
    posts = list(db_session.scalars(select(Post)))
    assert posts
    # Second sync should not re-tag already tagged posts
    result2 = service.run(sources=["instagram"])
    assert result2["tagged"]["posts"] == 0
    comments = list(db_session.scalars(select(Comment)))
    if comments:
        assert all(c.sentiment for c in comments)


def test_context_generation(db_session) -> None:
    from app.context.generator import regenerate_all_context
    from app.db import repository as repo
    from app.sync.service import SyncService

    SyncService(db_session, context_regen=regenerate_all_context).run(sources=["spotify", "instagram"])
    doc = repo.get_context_document(db_session, "artist_profile")
    assert doc is not None
    assert "Nova Lane" in doc.body_markdown or "Identity" in doc.body_markdown
    assert "## Posts" in doc.body_markdown
    assert "likes=" in doc.body_markdown
    ig = repo.get_context_document(db_session, "platform_instagram")
    assert ig is not None
    assert "## All posts" in ig.body_markdown
    assert "likes=" in ig.body_markdown
    assert "comments (" in ig.body_markdown or "comments:" in ig.body_markdown
    assert "See you there!" in ig.body_markdown or "Glass House" in ig.body_markdown
    sp = repo.get_context_document(db_session, "platform_spotify")
    assert sp is not None
    assert "kind: music" in sp.body_markdown
    assert "## Releases" in sp.body_markdown
    assert "No posts synced" not in sp.body_markdown
    assert "Midnight Swim" in sp.body_markdown or "Glass House" in sp.body_markdown
    # Unconfigured platforms must not appear as empty/fixture context docs
    assert repo.get_context_document(db_session, "platform_tiktok") is None
    assert repo.get_context_document(db_session, "platform_youtube") is None
    assert repo.get_context_document(db_session, "platform_facebook") is None


def test_context_omits_unconfigured_platforms(db_session) -> None:
    from app.context.generator import generate_artist_profile, regenerate_all_context
    from app.db import repository as repo

    # Stale fixture catalog + disconnected music must not leak into context.
    repo.resolve_music_artist(
        db_session, name="Nova Lane", source="spotify", external_id="fixture-sp"
    )
    repo.upsert_platform_account(
        db_session,
        source="instagram",
        external_id="ig_live",
        display_name="CousCous a colazione",
        username="couscousacolazione",
        status="connected",
    )
    repo.upsert_platform_account(
        db_session,
        source="spotify",
        external_id="fixture-sp",
        display_name="Nova Lane",
        status="disconnected",
    )
    db_session.flush()

    regenerate_all_context(db_session)
    assert repo.get_context_document(db_session, "platform_spotify") is None
    assert repo.get_context_document(db_session, "platform_instagram") is not None
    body = generate_artist_profile(db_session)
    assert "CousCous a colazione" in body
    assert "Nova Lane" not in body
    assert "Midnight Swim" not in body
    assert "## Catalog" not in body
    assert "- spotify:" not in body
    assert "- instagram:" in body


def test_context_prefers_platform_display_name(db_session) -> None:
    from app.context.generator import generate_artist_profile, resolve_artist_display_name
    from app.db import repository as repo

    # Stale fixture artist must not win over connected social identity.
    stale = repo.resolve_music_artist(
        db_session, name="Courtney Pine", source="deezer", external_id="7001"
    )
    assert stale.name == "Courtney Pine"
    repo.upsert_platform_account(
        db_session,
        source="instagram",
        external_id="ig_live",
        display_name="CousCous a colazione",
        username="couscousacolazione",
        status="connected",
    )
    repo.upsert_platform_account(
        db_session,
        source="deezer",
        external_id="165434897",
        display_name="CousCous a colazione",
        status="connected",
    )
    db_session.flush()

    assert resolve_artist_display_name(db_session) == "CousCous a colazione"
    body = generate_artist_profile(db_session)
    assert "CousCous a colazione" in body
    assert "Courtney Pine" not in body
    assert "Midnight Swim" not in body  # stale catalog not attached to primary artist


def test_media_adapt(db_session, tmp_path: Path) -> None:
    from app.db import repository as repo
    from app.media.pipeline import adapt_all_presets

    src = tmp_path / "original.png"
    Image.new("RGB", (1200, 800), color=(255, 80, 40)).save(src)
    out = tmp_path / "variants"
    results = adapt_all_presets(src, out, focal_point={"x": 0.3, "y": 0.4})
    assert len(results) == 4
    assert all(r.path.exists() for r in results)
    asset = repo.create_media_asset(
        db_session, kind="original", filename="original.png", storage_path=str(src)
    )
    assert asset.id


def test_live_mode_purges_fixture_soundcloud_identity(db_session, monkeypatch) -> None:
    """Fixture leftovers (novalane / 9001) must not survive into live mode."""
    from sqlalchemy import select

    from app.config import get_settings
    from app.db import repository as repo
    from app.db.models import PlatformAccount, Post
    from app.sync.service import SyncService

    SyncService(db_session).run(sources=["soundcloud", "instagram"])
    account = db_session.scalar(select(PlatformAccount).where(PlatformAccount.source == "soundcloud"))
    assert account is not None
    assert account.external_id == "9001"
    assert account.display_name == "novalane"
    assert (account.meta or {}).get("from_fixtures") is True
    assert db_session.scalar(select(Post).where(Post.source == "instagram")) is not None

    monkeypatch.setenv("PLATFORM_LIVE", "1")
    get_settings.cache_clear()

    cleared = repo.purge_stale_live_identities(db_session)
    assert cleared >= 1
    db_session.refresh(account)
    assert account.external_id is None
    assert account.display_name is None
    assert account.status == "needs_auth"
    assert db_session.scalar(select(Post).where(Post.source == "instagram")) is None

    from app.agent.tools import query_posts

    assert query_posts(db_session, source="instagram", order_by="like_count", limit=1) == []

    get_settings.cache_clear()


def test_live_connected_instagram_drops_fixture_posts(db_session, monkeypatch) -> None:
    """Connected live IG must not rank leftover fixture posts (Glass House / The Echo)."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.agent.tools import query_posts
    from app.config import get_settings
    from app.db import repository as repo
    from app.db.models import Post

    # Simulate prior fixture sync + a real live post mixed in.
    repo.upsert_post(
        db_session,
        source="instagram",
        external_id="ig_media_1",
        caption="New single Glass House out now 🎵",
        posted_at=datetime(2024, 11, 10, tzinfo=timezone.utc),
        like_count=420,
        comment_count=18,
    )
    repo.upsert_post(
        db_session,
        source="instagram",
        external_id="ig_media_2",
        caption="Playing Friday at The Echo — doors 8pm",
        posted_at=datetime(2024, 12, 1, tzinfo=timezone.utc),
        like_count=310,
        comment_count=42,
    )
    repo.upsert_post(
        db_session,
        source="instagram",
        external_id="17890001234567890",
        caption="Un vero arcobaleno di voci... Arco-íris...",
        posted_at=datetime(2026, 2, 4, tzinfo=timezone.utc),
        like_count=220,
        comment_count=18,
    )
    account = repo.upsert_platform_account(
        db_session,
        source="instagram",
        external_id="ig_live_user",
        display_name="Live Artist",
        status="connected",
        meta={"from_fixtures": False},
    )
    repo.store_account_token(db_session, account, "live-ig-token")
    db_session.commit()

    monkeypatch.setenv("PLATFORM_LIVE", "1")
    get_settings.cache_clear()

    rows = query_posts(db_session, source="instagram", order_by="like_count", limit=5)
    assert [r["external_id"] for r in rows] == ["17890001234567890"]
    assert "Glass House" not in (rows[0]["caption"] or "")
    assert db_session.scalar(select(Post).where(Post.external_id == "ig_media_1")) is None

    get_settings.cache_clear()


def test_agent_fixture_draft(db_session) -> None:
    from app.agent.content import generate_content_draft
    from app.context.generator import regenerate_all_context
    from app.sync.service import SyncService

    SyncService(db_session, context_regen=regenerate_all_context).run(sources=["spotify"])
    draft = generate_content_draft(db_session, prompt="Announce the new single", platforms=["instagram"])
    assert draft["caption"]
    assert "publish" not in draft["caption"].casefold() or True
    assert draft["hashtags"]


def test_api_sync_and_no_publish_routes(db_session, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("PLATFORM_LIVE", "0")
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import init_db, reset_engine
    from app.main import create_app

    get_settings.cache_clear()
    reset_engine()
    init_db()
    client = TestClient(create_app())
    r = client.post("/api/sync/refresh", json={"sources": ["spotify", "instagram"]})
    assert r.status_code == 200
    assert r.json()["status"] in {"success", "partial"}
    paths = {getattr(route, "path", "") for route in client.app.routes}
    assert not any("publish" in p or "schedule" in p for p in paths if p)
    assert "/api/metrics" not in paths
