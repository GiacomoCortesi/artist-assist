"""Meta env → DB bootstrap tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models import EncryptedToken, PlatformAccount
from app.security.bootstrap import bootstrap_meta_tokens_from_env
from app.security.tokens import decrypt_token


@pytest.fixture()
def db_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv(
        "TOKEN_ENCRYPTION_KEY",
        "test-encryption-key-for-artistassist-unit-tests",
    )
    monkeypatch.setenv("META_PAGE_ACCESS_TOKEN", "page-token-xyz")
    monkeypatch.setenv("META_PAGE_ID", "fb-page-1")
    monkeypatch.setenv("META_IG_USER_ID", "ig-user-1")
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "threads-token-abc")
    monkeypatch.setenv("THREADS_USER_ID", "th-user-1")
    from app.config import Settings, get_settings
    from app.db import get_session_factory, init_db, reset_engine

    get_settings.cache_clear()
    reset_engine()
    init_db()
    Session = get_session_factory()
    session = Session()
    try:
        yield session, Settings()
        session.commit()
    finally:
        session.close()
        reset_engine()
        get_settings.cache_clear()


def test_bootstrap_meta_tokens_from_env(db_session) -> None:
    session, settings = db_session
    bootstrap_meta_tokens_from_env(session, settings)
    session.flush()

    fb = session.scalar(select(PlatformAccount).where(PlatformAccount.source == "facebook"))
    ig = session.scalar(select(PlatformAccount).where(PlatformAccount.source == "instagram"))
    th = session.scalar(select(PlatformAccount).where(PlatformAccount.source == "threads"))
    assert fb is not None and fb.external_id == "fb-page-1" and fb.status == "connected"
    assert ig is not None and ig.external_id == "ig-user-1"
    assert th is not None and th.external_id == "th-user-1"

    fb_token = session.scalar(select(EncryptedToken).where(EncryptedToken.account_id == fb.id))
    assert fb_token is not None
    assert decrypt_token(fb_token.ciphertext) == "page-token-xyz"
    assert "page-token" not in fb_token.ciphertext
