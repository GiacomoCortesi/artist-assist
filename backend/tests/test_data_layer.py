"""Data layer unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, select


# Isolate test DB before app imports settings
@pytest.fixture()
def db_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv(
        "TOKEN_ENCRYPTION_KEY",
        "test-encryption-key-for-artistassist-unit-tests",
    )
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


def test_schema_creates_expected_tables(db_session) -> None:
    from app.db import get_engine

    names = set(inspect(get_engine()).get_table_names())
    expected = {
        "platform_accounts",
        "encrypted_tokens",
        "posts",
        "comments",
        "media_assets",
        "music_artists",
        "music_releases",
        "music_tracks",
        "topic_tags",
        "post_topic_tags",
        "context_documents",
        "content_plans",
        "content_drafts",
        "agent_threads",
        "agent_messages",
        "sync_runs",
        "app_settings",
    }
    assert expected.issubset(names)
    assert "publish_queue" not in names
    assert "scheduled_posts" not in names


def test_sqlite_uses_wal(db_session) -> None:
    from sqlalchemy import text

    from app.db import get_engine

    with get_engine().connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
    assert str(mode).lower() == "wal"


def test_token_round_trip(db_session) -> None:
    from app.db import repository as repo
    from app.security.tokens import decrypt_token, encrypt_token

    plain = "oauth-access-token-xyz"
    cipher = encrypt_token(plain)
    assert cipher != plain
    assert decrypt_token(cipher) == plain

    account = repo.upsert_platform_account(db_session, source="spotify", external_id="sp1")
    repo.store_account_token(db_session, account, plain)
    db_session.commit()

    # Ciphertext only in DB
    from app.db.models import EncryptedToken

    row = db_session.scalar(select(EncryptedToken))
    assert row is not None
    assert row.ciphertext != plain
    assert "oauth-access" not in row.ciphertext
    assert repo.load_account_token(db_session, account) == plain


def test_crud_major_entities(db_session) -> None:
    from app.db import repository as repo

    account = repo.upsert_platform_account(
        db_session, source="instagram", external_id="ig1", display_name="Artist"
    )
    post = repo.upsert_post(
        db_session, source="instagram", external_id="p1", caption="Hello gig Friday"
    )
    repo.add_comment(
        db_session, post, source="instagram", external_id="c1", body="Can't wait", sentiment="positive"
    )
    asset = repo.create_media_asset(
        db_session,
        kind="original",
        filename="shot.jpg",
        storage_path="storage/shot.jpg",
        source_post_id=post.id,
    )
    artist = repo.get_or_create_music_artist(db_session, "Test Artist")
    artist.spotify_id = "spot123"
    release = repo.upsert_music_release(
        db_session,
        title="Debut",
        normalized_title="debut",
        release_date="2024-01-01",
        artist_id=artist.id,
        source="spotify",
        source_id="alb1",
    )
    track = repo.upsert_music_track(
        db_session,
        title="Track 1",
        normalized_title="track 1",
        release_id=release.id,
        artist_id=artist.id,
        source="spotify",
        source_id="tr1",
    )
    topic = repo.ensure_topic(db_session, "gig", "Gig")
    doc = repo.upsert_context_document(
        db_session, slug="artist_profile", title="Artist Profile", body_markdown="# Hello"
    )
    run = repo.create_sync_run(db_session)
    draft = repo.create_draft(db_session, title="Caption draft", caption="hi")

    db_session.commit()

    assert account.id
    assert post.id
    assert asset.kind == "original"
    assert release.spotify_id == "alb1"
    assert track.spotify_id == "tr1"
    assert topic.slug == "gig"
    assert doc.body_markdown.startswith("#")
    assert run.status == "running"
    assert draft.status == "draft"
    # No MBID / last.fm columns on artist
    assert not hasattr(artist, "mbid")
    assert not hasattr(artist, "lastfm_id")


def test_resolve_music_artist_by_platform_id(db_session) -> None:
    from app.db import repository as repo
    from app.db.models import MusicArtist

    first = repo.resolve_music_artist(
        db_session,
        name="Nova Lane",
        source="deezer",
        external_id="7001",
    )
    db_session.flush()
    assert first.deezer_id == "7001"

    # Name mismatch must not create a second row with the same deezer_id.
    second = repo.resolve_music_artist(
        db_session,
        name="nova lane",
        source="deezer",
        external_id="7001",
    )
    db_session.flush()
    assert second.id == first.id
    assert db_session.scalar(select(MusicArtist)).id == first.id


def test_music_merge_by_normalized_title(db_session) -> None:
    from app.db import repository as repo

    r1 = repo.upsert_music_release(
        db_session,
        title="My Album",
        normalized_title="my album",
        release_date="2023",
        source="spotify",
        source_id="s1",
    )
    r2 = repo.upsert_music_release(
        db_session,
        title="My Album (Deluxe)",
        normalized_title="my album",
        release_date="2023",
        source="deezer",
        source_id="d1",
    )
    assert r1.id == r2.id
    assert r2.source_ids["spotify"] == "s1"
    assert r2.source_ids["deezer"] == "d1"
