"""Interactive agent chat thread tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db import repository as repo


@pytest.fixture(autouse=True)
def clear_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LLM_LIVE", "0")
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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
    finally:
        session.close()
        reset_engine()
        get_settings.cache_clear()


def _seed_ig(session) -> None:
    high = repo.upsert_post(
        session,
        source="instagram",
        external_id="ig-high",
        caption="Winner post",
        posted_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        like_count=999,
        comment_count=3,
    )
    low = repo.upsert_post(
        session,
        source="instagram",
        external_id="ig-low",
        caption="Quiet post",
        posted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        like_count=10,
        comment_count=50,
    )
    repo.add_comment(
        session,
        low,
        source="instagram",
        external_id="c-neg",
        author_name="hater",
        body="This is terrible, hate it",
        commented_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        sentiment="negative",
        theme="complaint",
    )
    repo.add_comment(
        session,
        high,
        source="instagram",
        external_id="c-pos",
        author_name="fan",
        body="Love this, amazing!",
        commented_at=datetime(2024, 6, 2, tzinfo=timezone.utc),
        sentiment="positive",
        theme="praise",
    )
    session.commit()


def test_multi_turn_history_fixture(db_session) -> None:
    from app.agent.chat import run_turn

    _seed_ig(db_session)
    thread = repo.create_thread(db_session, title="Test")
    first = run_turn(db_session, thread, "Which Instagram post has the most likes?")
    assert "ig-high" in first["content"]
    assert "999" in first["content"]

    second = run_turn(db_session, thread, "Thanks — now draft a caption celebrating that win")
    assert second["drafts"] or "draft" in second["content"].casefold()
    msgs = repo.list_messages(db_session, thread.id)
    roles = [m.role for m in msgs]
    assert roles.count("user") == 2
    assert roles.count("assistant") == 2


def test_fixture_reviews_negative_comments(db_session) -> None:
    from app.agent.chat import run_turn

    _seed_ig(db_session)
    thread = repo.create_thread(db_session, title="Comments")
    result = run_turn(
        db_session,
        thread,
        "Are there any negative Instagram comments I should worry about?",
    )
    assert "query_comments" in result["content"]
    assert "terrible" in result["content"].casefold()
    assert "hater" in result["content"].casefold()
    assert "aggregate" not in result["content"].casefold()


def test_api_thread_message(db_session, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LLM_LIVE", "0")
    monkeypatch.setenv("PLATFORM_LIVE", "0")
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import init_db, reset_engine
    from app.main import create_app

    get_settings.cache_clear()
    reset_engine()
    init_db()
    client = TestClient(create_app())

    # Seed via API session — use sync fixtures then ask
    client.post("/api/sync/refresh", json={"sources": ["instagram"]})
    created = client.post("/api/studio/threads", json={"title": "Stats"})
    assert created.status_code == 200
    tid = created.json()["id"]
    r = client.post(
        f"/api/studio/threads/{tid}/messages",
        json={"content": "Which Instagram post has the most likes?"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "content" in body
    detail = client.get(f"/api/studio/threads/{tid}")
    assert detail.status_code == 200
    assert len(detail.json()["messages"]) >= 2


def test_stream_endpoint_emits_events(db_session, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'stream.db'}")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LLM_LIVE", "0")
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.db import init_db, reset_engine
    from app.main import create_app

    get_settings.cache_clear()
    reset_engine()
    init_db()
    client = TestClient(create_app())
    tid = client.post("/api/studio/threads", json={}).json()["id"]
    with client.stream(
        "POST",
        f"/api/studio/threads/{tid}/messages/stream",
        json={"content": "hello"},
    ) as res:
        assert res.status_code == 200
        raw = "".join(res.iter_text())
    assert "data:" in raw
    assert '"type": "done"' in raw or '"type":"done"' in raw


def test_live_tool_loop_with_history(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_LIVE", "1")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.config import get_settings

    get_settings.cache_clear()
    _seed_ig(db_session)

    calls: list[dict] = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                tool_call = SimpleNamespace(
                    id="call_1",
                    function=SimpleNamespace(
                        name="query_posts",
                        arguments=json.dumps(
                            {"source": "instagram", "order_by": "like_count", "limit": 1}
                        ),
                    ),
                )
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content=None, tool_calls=[tool_call])
                        )
                    ]
                )
            tool_msg = next(m for m in kwargs["messages"] if m.get("role") == "tool")
            payload = json.loads(tool_msg["content"])
            assert payload["posts"][0]["external_id"] == "ig-high"
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content="Top IG post is ig-high with 999 likes.",
                            tool_calls=None,
                        )
                    )
                ]
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("app.agent.llm.OpenAI", FakeClient)

    from app.agent.chat import run_turn

    thread = repo.create_thread(db_session)
    result = run_turn(db_session, thread, "Which Instagram post has the most likes?")
    assert "ig-high" in result["content"]
    assert len(calls) == 2
