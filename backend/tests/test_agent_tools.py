"""Agent tools + tool-calling loop tests."""

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


def _seed_posts(session) -> None:
    repo.upsert_post(
        session,
        source="instagram",
        external_id="ig-low",
        caption="Low likes post",
        posted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        like_count=10,
        comment_count=50,
        permalink="https://instagram.com/p/low",
    )
    repo.upsert_post(
        session,
        source="instagram",
        external_id="ig-high",
        caption="High likes post about Glass House",
        posted_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        like_count=999,
        comment_count=3,
        permalink="https://instagram.com/p/high",
    )
    repo.upsert_post(
        session,
        source="instagram",
        external_id="ig-null",
        caption="No metrics yet",
        posted_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        like_count=None,
        comment_count=None,
    )
    repo.upsert_post(
        session,
        source="tiktok",
        external_id="tt-1",
        caption="TikTok viral",
        posted_at=datetime(2024, 8, 1, tzinfo=timezone.utc),
        like_count=5000,
        comment_count=100,
    )
    session.commit()


def test_query_posts_most_likes_instagram(db_session) -> None:
    from app.agent.tools import query_posts

    _seed_posts(db_session)
    rows = query_posts(db_session, source="instagram", order_by="like_count", order="desc", limit=1)
    assert len(rows) == 1
    assert rows[0]["external_id"] == "ig-high"
    assert rows[0]["like_count"] == 999
    assert "Glass House" in (rows[0]["caption"] or "")


def test_query_posts_nulls_sort_last(db_session) -> None:
    from app.agent.tools import query_posts

    _seed_posts(db_session)
    rows = query_posts(db_session, source="instagram", order_by="like_count", order="desc", limit=10)
    assert [r["external_id"] for r in rows] == ["ig-high", "ig-low", "ig-null"]


def test_query_posts_top_comments(db_session) -> None:
    from app.agent.tools import query_posts

    _seed_posts(db_session)
    rows = query_posts(db_session, source="instagram", order_by="comment_count", limit=1)
    assert rows[0]["external_id"] == "ig-low"
    assert rows[0]["comment_count"] == 50


def _seed_comments(session) -> None:
    high = repo.upsert_post(
        session,
        source="instagram",
        external_id="ig-high",
        caption="High likes post about Glass House",
        posted_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        like_count=999,
        comment_count=3,
        permalink="https://instagram.com/p/high",
    )
    low = repo.upsert_post(
        session,
        source="instagram",
        external_id="ig-low",
        caption="Low likes post",
        posted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        like_count=10,
        comment_count=50,
        permalink="https://instagram.com/p/low",
    )
    repo.add_comment(
        session,
        high,
        source="instagram",
        external_id="c-pos",
        author_name="fan1",
        body="Love this track, amazing!",
        commented_at=datetime(2024, 6, 2, tzinfo=timezone.utc),
        sentiment="positive",
        theme="praise",
    )
    repo.add_comment(
        session,
        low,
        source="instagram",
        external_id="c-neg",
        author_name="hater",
        body="This is terrible, worst single ever",
        commented_at=datetime(2024, 6, 3, tzinfo=timezone.utc),
        sentiment="negative",
        theme="complaint",
    )
    repo.add_comment(
        session,
        high,
        source="instagram",
        external_id="c-q",
        author_name="curious",
        body="When is the next show?",
        commented_at=datetime(2024, 6, 4, tzinfo=timezone.utc),
        sentiment="neutral",
        theme="question",
    )
    session.commit()


def test_query_comments_by_sentiment(db_session) -> None:
    from app.agent.tools import query_comments

    _seed_comments(db_session)
    rows = query_comments(db_session, source="instagram", sentiment="negative", limit=5)
    assert len(rows) == 1
    assert rows[0]["external_id"] == "c-neg"
    assert "terrible" in (rows[0]["body"] or "")
    assert rows[0]["theme"] == "complaint"
    assert rows[0]["post_external_id"] == "ig-low"


def test_query_comments_by_theme_and_post(db_session) -> None:
    from app.agent.tools import query_comments

    _seed_comments(db_session)
    rows = query_comments(
        db_session,
        post_external_id="ig-high",
        theme="question",
        limit=5,
    )
    assert len(rows) == 1
    assert rows[0]["external_id"] == "c-q"
    assert "next show" in (rows[0]["body"] or "")


def test_execute_tool_query_comments(db_session) -> None:
    from app.agent.tools import AGENT_TOOLS, execute_tool

    _seed_comments(db_session)
    raw = execute_tool(
        db_session,
        "query_comments",
        {"source": "instagram", "sentiment": "positive", "limit": 5},
    )
    payload = json.loads(raw)
    assert payload["count"] == 1
    assert payload["comments"][0]["external_id"] == "c-pos"
    assert "query_comments" in {t["name"] for t in AGENT_TOOLS}


def test_execute_tool_json(db_session) -> None:
    from app.agent.tools import execute_tool

    _seed_posts(db_session)
    raw = execute_tool(
        db_session,
        "query_posts",
        {"source": "instagram", "order_by": "like_count", "limit": 1},
    )
    payload = json.loads(raw)
    assert payload["count"] == 1
    assert payload["posts"][0]["external_id"] == "ig-high"


def test_fixture_stats_answer_uses_sqlite(db_session) -> None:
    from app.agent.content import generate_content_draft

    _seed_posts(db_session)
    draft = generate_content_draft(
        db_session,
        prompt="Which Instagram post has the most likes?",
        platforms=["instagram"],
    )
    assert "ig-high" in draft["caption"]
    assert "999" in draft["caption"]
    assert "Glass House" in draft["caption"]
    assert draft.get("thread_id")
    assert "ig-high" in (draft.get("reply") or draft["caption"])


def test_openai_tool_loop_calls_query_posts(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_LIVE", "1")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.config import get_settings

    get_settings.cache_clear()
    _seed_posts(db_session)

    calls: list[dict] = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                # First turn: request tool
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
            # Second turn: final answer using tool result
            tool_msg = next(m for m in kwargs["messages"] if m.get("role") == "tool")
            payload = json.loads(tool_msg["content"])
            assert payload["posts"][0]["external_id"] == "ig-high"
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=(
                                "The Instagram post with the most likes is "
                                f"{payload['posts'][0]['external_id']} "
                                f"with {payload['posts'][0]['like_count']} likes."
                            ),
                            tool_calls=None,
                        )
                    )
                ]
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("app.agent.llm.OpenAI", FakeClient)

    from app.agent.content import generate_content_draft

    draft = generate_content_draft(
        db_session,
        prompt="Which Instagram post has the most likes?",
        platforms=["instagram"],
    )
    assert "ig-high" in draft["caption"]
    assert "999" in draft["caption"]
    assert len(calls) == 2
    assert calls[0].get("tools")
