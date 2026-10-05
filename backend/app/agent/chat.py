"""Interactive Content Studio agent — threaded chat with tools."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from typing import Any

from sqlalchemy.orm import Session

from app.agent.llm import SYSTEM_PROMPT, llm_configured, run_tool_loop
from app.agent.tools import ToolContext, compact_identity_blurb, execute_tool
from app.config import get_settings
from app.db import repository as repo
from app.db.models import AgentThread

EventCallback = Callable[[str, dict[str, Any]], None]

_HISTORY_LIMIT = 40


def _system_prompt(session: Session) -> str:
    identity = compact_identity_blurb(session)
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"{identity}\n"
        "Tools: query_posts, query_comments, list_context_docs, get_context_doc, "
        "list_releases, upsert_draft, get_draft."
    )


def _history_as_openai_messages(session: Session, thread_id: int) -> list[dict[str, Any]]:
    """Rebuild OpenAI-style messages from persisted turns (user/assistant/tool)."""
    msgs = repo.list_messages(session, thread_id)
    # Keep a trailing window so prompts stay bounded
    if len(msgs) > _HISTORY_LIMIT:
        msgs = msgs[-_HISTORY_LIMIT:]
    out: list[dict[str, Any]] = []
    for m in msgs:
        if m.role == "user":
            out.append({"role": "user", "content": m.content or ""})
        elif m.role == "assistant":
            item: dict[str, Any] = {"role": "assistant", "content": m.content}
            if m.tool_calls:
                item["tool_calls"] = m.tool_calls
            out.append(item)
        elif m.role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id or "",
                    "content": m.content or "",
                }
            )
    return out


def _fixture_reply(session: Session, user_text: str, ctx: ToolContext) -> str:
    """Deterministic offline agent: use tools for rankings / drafts when obvious."""
    lower = user_text.casefold()

    comment_intent = any(
        k in lower
        for k in (
            "comment text",
            "comments say",
            "negative comment",
            "hateful",
            "hate comment",
            "sentiment",
            "what are people saying",
            "read comment",
            "review comment",
            "complaint",
            "praise",
        )
    ) or (
        "comment" in lower
        and any(k in lower for k in ("negative", "hate", "toxic", "mean", "bad", "positive"))
    )
    if comment_intent:
        source = None
        for candidate in ("instagram", "facebook", "threads", "youtube"):
            if candidate in lower:
                source = candidate
                break
        args: dict[str, Any] = {"limit": 10}
        if source:
            args["source"] = source
        if any(k in lower for k in ("negative", "hate", "hateful", "toxic", "mean", "complaint")):
            args["sentiment"] = "negative"
        elif "positive" in lower or "praise" in lower:
            args["sentiment"] = "positive"
        if "question" in lower:
            args["theme"] = "question"
        elif "complaint" in lower:
            args["theme"] = "complaint"
        elif "praise" in lower:
            args["theme"] = "praise"
        raw = execute_tool(session, "query_comments", args, ctx=ctx)
        payload = json.loads(raw)
        comments = payload.get("comments") or []
        if not comments:
            filters = ", ".join(f"{k}={v}" for k, v in args.items() if k != "limit")
            return (
                f"No synced comments found"
                f"{f' ({filters})' if filters else ''}. "
                "Sync Instagram/Facebook/Threads/YouTube first, then ask again."
            )
        lines = ["From synced data (`query_comments`):"]
        for i, row in enumerate(comments, start=1):
            author = row.get("author_name") or "unknown"
            tags = []
            if row.get("sentiment"):
                tags.append(f"sentiment={row['sentiment']}")
            if row.get("theme"):
                tags.append(f"theme={row['theme']}")
            tag_s = f" ({', '.join(tags)})" if tags else ""
            lines.append(
                f"{i}. [{row['source']}] @{author}{tag_s} on post "
                f"`{row.get('post_external_id')}`: {row.get('body') or '(empty)'}"
            )
        lines.append("(Mock agent — set LLM_LIVE=1 for the live model.)")
        return "\n".join(lines)

    if any(
        k in lower
        for k in (
            "most like",
            "most likes",
            "top ",
            "highest",
            "engagement",
            "like count",
            "which post",
            "stats",
        )
    ):
        source = None
        for candidate in ("instagram", "facebook", "threads", "tiktok", "youtube"):
            if candidate in lower:
                source = candidate
                break
        order_by = "like_count"
        if "comment" in lower and "like" not in lower:
            order_by = "comment_count"
        elif "view" in lower and "like" not in lower:
            order_by = "view_count"
        limit = 1
        m = re.search(r"\btop\s+(\d+)\b", user_text, re.IGNORECASE)
        if m:
            limit = max(1, min(int(m.group(1)), 10))
        raw = execute_tool(
            session,
            "query_posts",
            {"source": source, "order_by": order_by, "limit": limit},
            ctx=ctx,
        )
        payload = json.loads(raw)
        posts = payload.get("posts") or []
        if not posts:
            return f"No synced posts found for {source or 'any platform'}. Sync first, then ask again."
        lines = [f"From synced data (`query_posts`, order_by={order_by}):"]
        for i, row in enumerate(posts, start=1):
            lines.append(
                f"{i}. [{row['source']}] {order_by}={row.get(order_by)} · "
                f"id=`{row['external_id']}` · {row.get('caption') or '(no caption)'}"
            )
            if row.get("permalink"):
                lines.append(f"   {row['permalink']}")
        lines.append("(Mock agent — set LLM_LIVE=1 for the live model.)")
        return "\n".join(lines)

    if any(k in lower for k in ("draft", "caption", "write", "announce", "post about")):
        caption = (
            f"{user_text.strip()}\n\n"
            f"— grounded stub for {compact_identity_blurb(session)}. "
            "(Mock agent — set LLM_LIVE=1 for live model.)"
        )
        result = json.loads(
            execute_tool(
                session,
                "upsert_draft",
                {
                    "title": user_text.strip()[:80] or "Untitled draft",
                    "caption": caption,
                    "hashtags": ["#music", "#newmusic"],
                    "platforms": ["instagram"],
                },
                ctx=ctx,
            )
        )
        return (
            f"Saved draft #{result.get('id')}.\n\n{caption}\n\n"
            "Say if you want a different platform tone or a shorter cut."
        )

    return (
        "I'm your Content Studio agent (mock mode). Ask me to draft a caption, "
        "adapt tone for a platform, query synced post stats "
        "(e.g. which Instagram post has the most likes), or review synced comments "
        "(e.g. any negative Instagram comments). "
        "Set LLM_LIVE=1 for the live model."
    )


def run_turn(
    session: Session,
    thread: AgentThread,
    user_text: str,
    *,
    on_event: EventCallback | None = None,
) -> dict[str, Any]:
    """Persist user message, run agent, persist assistant reply. Returns summary."""
    text = (user_text or "").strip()
    if not text:
        raise ValueError("Message cannot be empty")

    if not thread.title or thread.title == "Studio chat":
        thread.title = text[:80]

    user_msg = repo.add_message(session, thread, role="user", content=text)
    if on_event:
        on_event("user", {"id": user_msg.id, "content": text})

    ctx = ToolContext(session, thread_id=thread.id)
    settings = get_settings()
    events: list[tuple[str, dict[str, Any]]] = []

    def _capture(event_type: str, data: dict[str, Any]) -> None:
        events.append((event_type, data))
        if on_event:
            on_event(event_type, data)
        if event_type == "draft_updated":
            return
        # Surface draft updates from tool ctx after tools run

    if llm_configured(settings):
        history = _history_as_openai_messages(session, thread.id)
        reply = run_tool_loop(
            session=session,
            messages=history,
            system_content=_system_prompt(session),
            settings=settings,
            tool_ctx=ctx,
            on_event=_capture,
        )
    else:
        # Emit synthetic tool events so UI stays consistent in mock mode
        lower = text.casefold()
        if any(
            k in lower
            for k in (
                "comment text",
                "negative comment",
                "hateful",
                "sentiment",
                "what are people saying",
                "complaint",
                "praise",
            )
        ) or ("comment" in lower and any(k in lower for k in ("negative", "hate", "toxic", "mean"))):
            _capture("tool_start", {"name": "query_comments", "arguments": {}})
        elif "like" in lower or "stats" in lower:
            _capture("tool_start", {"name": "query_posts", "arguments": {}})
        reply = _fixture_reply(session, text, ctx)
        _capture("message", {"content": reply})

    for draft in ctx.draft_updates:
        _capture("draft_updated", {"draft": draft})

    assistant_msg = repo.add_message(
        session,
        thread,
        role="assistant",
        content=reply,
        meta={"fixture": not llm_configured(settings), "tools_used": [d for d, _ in events if d == "tool_start"]},
    )
    session.commit()

    if on_event:
        on_event(
            "done",
            {
                "message_id": assistant_msg.id,
                "thread_id": thread.id,
                "content": reply,
            },
        )

    return {
        "thread_id": thread.id,
        "user_message_id": user_msg.id,
        "assistant_message_id": assistant_msg.id,
        "content": reply,
        "drafts": list(ctx.draft_updates),
    }


def iter_turn_events(
    session: Session,
    thread: AgentThread,
    user_text: str,
) -> Iterator[dict[str, Any]]:
    """Yield SSE-shaped event payloads for a turn."""
    queue: list[dict[str, Any]] = []

    def on_event(event_type: str, data: dict[str, Any]) -> None:
        queue.append({"type": event_type, **data})

    result = run_turn(session, thread, user_text, on_event=on_event)
    yield from queue
    # Ensure a terminal done exists
    if not any(e.get("type") == "done" for e in queue):
        yield {
            "type": "done",
            "thread_id": result["thread_id"],
            "message_id": result["assistant_message_id"],
            "content": result["content"],
        }


def thread_to_dict(thread: AgentThread, *, include_messages: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": thread.id,
        "title": thread.title,
        "status": thread.status,
        "created_at": thread.created_at.isoformat() if thread.created_at else None,
        "updated_at": thread.updated_at.isoformat() if thread.updated_at else None,
    }
    if include_messages:
        payload["messages"] = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "tool_name": m.tool_name,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in thread.messages
            if m.role in {"user", "assistant"}
        ]
    return payload
