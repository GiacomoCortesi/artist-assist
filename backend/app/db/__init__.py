"""Database session and schema bootstrap (create_all on startup)."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _sqlite_url(url: str) -> str:
    # Ensure parent dir exists for file-backed sqlite
    if url.startswith("sqlite:///"):
        path = url.removeprefix("sqlite:///")
        if path != ":memory:" and not path.startswith("//"):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    return url


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        url = _sqlite_url(settings.database_url)
        connect_args: dict[str, object] = {}
        if url.startswith("sqlite"):
            # Avoid "database is locked" under concurrent API + long sync.
            connect_args = {"check_same_thread": False, "timeout": 60.0}
        _engine = create_engine(url, connect_args=connect_args, future=True)

        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
            if url.startswith("sqlite"):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=60000")
                cursor.close()

        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def init_db() -> None:
    """Create all tables if missing. Choice: SQLAlchemy create_all (no Alembic for MVP)."""
    from sqlalchemy import inspect, text

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    # Lightweight additive migrations for existing SQLite files (create_all skips new columns).
    if engine.dialect.name == "sqlite":
        insp = inspect(engine)
        if "content_drafts" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("content_drafts")}
            if "thread_id" not in cols:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE content_drafts ADD COLUMN thread_id INTEGER"))


def reset_engine() -> None:
    """Test helper: dispose and clear cached engine."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
