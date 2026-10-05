"""Agent read/write tools — deterministic queries over synced SQLite data."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import repository as repo
from app.db.models import Comment, ContentDraft, ContextDocument, MusicRelease, PlatformAccount, Post

_ALLOWED_SOURCES = frozenset({"instagram", "facebook", "threads", "tiktok", "youtube"})
_COMMENT_SOURCES = frozenset({"instagram", "facebook", "threads", "youtube"})
_ALLOWED_ORDER_BY = frozenset({"like_count", "comment_count", "view_count", "posted_at"})
_ALLOWED_SENTIMENTS = frozenset({"positive", "negative", "neutral"})
_MAX_LIMIT = 20
_CAPTION_LIMIT = 200
_COMMENT_BODY_LIMIT = 500
_CONTEXT_MAX_CHARS = 6000

QUERY_POSTS_SCHEMA: dict[str, Any] = {
    "name": "query_posts",
    "description": (
        "Query synced social posts for exact engagement rankings "
        "(most likes, most comments by count, newest). Returns caption + counts only — "
        "use query_comments to read individual comment text/sentiment. Never invent metrics."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "enum": sorted(_ALLOWED_SOURCES),
                "description": "Platform filter (omit for all social sources).",
            },
            "order_by": {
                "type": "string",
                "enum": sorted(_ALLOWED_ORDER_BY),
                "description": "Sort field. Default: like_count.",
            },
            "order": {
                "type": "string",
                "enum": ["desc", "asc"],
                "description": "Sort direction. Default: desc.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": _MAX_LIMIT,
                "description": f"Max rows (1–{_MAX_LIMIT}). Default: 5.",
            },
        },
        "additionalProperties": False,
    },
}

QUERY_COMMENTS_SCHEMA: dict[str, Any] = {
    "name": "query_comments",
    "description": (
        "Query synced individual comments (full text, author, sentiment, theme). "
        "Use for community management: negative/hate review, praise themes, "
        "questions, or comments on a specific post. TikTok has no comments. "
        "Never invent comment text."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "enum": sorted(_COMMENT_SOURCES),
                "description": "Platform filter (omit for all comment-capable sources).",
            },
            "post_external_id": {
                "type": "string",
                "description": "Limit to comments on this post external_id.",
            },
            "sentiment": {
                "type": "string",
                "enum": sorted(_ALLOWED_SENTIMENTS),
                "description": "Filter by tagged sentiment (positive/negative/neutral).",
            },
            "theme": {
                "type": "string",
                "description": (
                    "Filter by tagged theme (e.g. praise, complaint, question, general)."
                ),
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": _MAX_LIMIT,
                "description": f"Max rows (1–{_MAX_LIMIT}). Default: 10.",
            },
        },
        "additionalProperties": False,
    },
}

LIST_CONTEXT_DOCS_SCHEMA: dict[str, Any] = {
    "name": "list_context_docs",
    "description": "List available artist context document slugs (profile, platforms).",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

GET_CONTEXT_DOC_SCHEMA: dict[str, Any] = {
    "name": "get_context_doc",
    "description": (
        "Load one context document by slug (e.g. artist_profile, platform_instagram). "
        "Use when you need tone, bio, or platform history beyond query_posts."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "slug": {
                "type": "string",
                "description": "Document slug from list_context_docs.",
            },
            "max_chars": {
                "type": "integer",
                "minimum": 500,
                "maximum": _CONTEXT_MAX_CHARS,
                "description": f"Truncate body to this many chars (default {_CONTEXT_MAX_CHARS}).",
            },
        },
        "required": ["slug"],
        "additionalProperties": False,
    },
}

LIST_RELEASES_SCHEMA: dict[str, Any] = {
    "name": "list_releases",
    "description": "List synced music releases (title, date, type) for grounded promo copy.",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 30,
                "description": "Max releases. Default: 12.",
            },
        },
        "additionalProperties": False,
    },
}

UPSERT_DRAFT_SCHEMA: dict[str, Any] = {
    "name": "upsert_draft",
    "description": (
        "Create or update a content draft the user can export. "
        "Call when they want a caption/post saved — not for every chat reply."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "draft_id": {
                "type": "integer",
                "description": "Existing draft id to update (omit to create).",
            },
            "title": {"type": "string"},
            "caption": {"type": "string"},
            "hashtags": {
                "type": "array",
                "items": {"type": "string"},
            },
            "platforms": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["caption"],
        "additionalProperties": False,
    },
}

GET_DRAFT_SCHEMA: dict[str, Any] = {
    "name": "get_draft",
    "description": "Load a saved draft by id.",
    "parameters": {
        "type": "object",
        "properties": {"draft_id": {"type": "integer"}},
        "required": ["draft_id"],
        "additionalProperties": False,
    },
}

AGENT_TOOLS: list[dict[str, Any]] = [
    QUERY_POSTS_SCHEMA,
    QUERY_COMMENTS_SCHEMA,
    LIST_CONTEXT_DOCS_SCHEMA,
    GET_CONTEXT_DOC_SCHEMA,
    LIST_RELEASES_SCHEMA,
    UPSERT_DRAFT_SCHEMA,
    GET_DRAFT_SCHEMA,
]


def _fmt_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat(timespec="seconds")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _truncate_caption(caption: str | None) -> str | None:
    if caption is None:
        return None
    text = caption.strip()
    if not text:
        return None
    if len(text) <= _CAPTION_LIMIT:
        return text
    return text[:_CAPTION_LIMIT].rstrip() + "…"


def _truncate_comment_body(body: str | None) -> str | None:
    if body is None:
        return None
    text = body.strip()
    if not text:
        return None
    if len(text) <= _COMMENT_BODY_LIMIT:
        return text
    return text[:_COMMENT_BODY_LIMIT].rstrip() + "…"


def query_posts(
    session: Session,
    *,
    source: str | None = None,
    order_by: str = "like_count",
    order: str = "desc",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return posts sorted by a metric. Null metric values sort last."""
    from app.config import get_settings

    # Live mode: never answer from leftover fixture rows.
    if not get_settings().use_fixtures:
        repo.purge_stale_live_identities(session)

    if source is not None and source not in _ALLOWED_SOURCES:
        raise ValueError(f"Unsupported source: {source}")
    if order_by not in _ALLOWED_ORDER_BY:
        raise ValueError(f"Unsupported order_by: {order_by}")
    if order not in {"desc", "asc"}:
        raise ValueError(f"Unsupported order: {order}")
    limit = max(1, min(int(limit), _MAX_LIMIT))

    col = getattr(Post, order_by)
    stmt = select(Post)
    if source is not None:
        stmt = stmt.where(Post.source == source)
    else:
        stmt = stmt.where(Post.source.in_(sorted(_ALLOWED_SOURCES)))

    # Live mode: only return posts for sources that are actually connected.
    if not get_settings().use_fixtures:
        accounts = {a.source: a for a in session.scalars(select(PlatformAccount))}
        candidates = [source] if source else sorted(_ALLOWED_SOURCES)
        ready = [src for src in candidates if repo.source_is_live_ready(session, accounts.get(src))]
        if not ready:
            return []
        stmt = stmt.where(Post.source.in_(ready))

    if order == "desc":
        stmt = stmt.order_by(col.desc().nulls_last(), Post.posted_at.desc().nulls_last())
    else:
        stmt = stmt.order_by(col.asc().nulls_last(), Post.posted_at.desc().nulls_last())
    stmt = stmt.limit(limit)

    rows: list[dict[str, Any]] = []
    for post in session.scalars(stmt):
        rows.append(
            {
                "source": post.source,
                "external_id": post.external_id,
                "posted_at": _fmt_dt(post.posted_at),
                "media_type": post.media_type,
                "like_count": post.like_count,
                "comment_count": post.comment_count,
                "view_count": post.view_count,
                "permalink": post.permalink,
                "caption": _truncate_caption(post.caption),
            }
        )
    return rows


def query_comments(
    session: Session,
    *,
    source: str | None = None,
    post_external_id: str | None = None,
    sentiment: str | None = None,
    theme: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Return synced comment rows with text + tags. Newest first."""
    from app.config import get_settings

    if not get_settings().use_fixtures:
        repo.purge_stale_live_identities(session)

    if source is not None and source not in _COMMENT_SOURCES:
        raise ValueError(f"Unsupported source for comments: {source}")
    if sentiment is not None and sentiment not in _ALLOWED_SENTIMENTS:
        raise ValueError(f"Unsupported sentiment: {sentiment}")
    theme_filter = (theme or "").strip() or None
    limit = max(1, min(int(limit), _MAX_LIMIT))

    stmt = select(Comment, Post).join(Post, Comment.post_id == Post.id)
    if source is not None:
        stmt = stmt.where(Comment.source == source)
    else:
        stmt = stmt.where(Comment.source.in_(sorted(_COMMENT_SOURCES)))

    if not get_settings().use_fixtures:
        accounts = {a.source: a for a in session.scalars(select(PlatformAccount))}
        candidates = [source] if source else sorted(_COMMENT_SOURCES)
        ready = [src for src in candidates if repo.source_is_live_ready(session, accounts.get(src))]
        if not ready:
            return []
        stmt = stmt.where(Comment.source.in_(ready))

    if post_external_id:
        stmt = stmt.where(Post.external_id == post_external_id.strip())
    if sentiment is not None:
        stmt = stmt.where(Comment.sentiment == sentiment)
    if theme_filter is not None:
        stmt = stmt.where(Comment.theme == theme_filter)

    stmt = stmt.order_by(Comment.commented_at.desc().nulls_last(), Comment.id.desc()).limit(limit)

    rows: list[dict[str, Any]] = []
    for comment, post in session.execute(stmt):
        rows.append(
            {
                "source": comment.source,
                "external_id": comment.external_id,
                "author_name": comment.author_name,
                "body": _truncate_comment_body(comment.body),
                "commented_at": _fmt_dt(comment.commented_at),
                "sentiment": comment.sentiment,
                "theme": comment.theme,
                "post_external_id": post.external_id,
                "post_permalink": post.permalink,
                "post_caption": _truncate_caption(post.caption),
            }
        )
    return rows


def list_context_docs(session: Session) -> list[dict[str, Any]]:
    docs = list(session.scalars(select(ContextDocument).order_by(ContextDocument.slug)))
    return [
        {
            "slug": d.slug,
            "title": d.title,
            "chars": len(d.body_markdown or ""),
        }
        for d in docs
    ]


def get_context_doc(
    session: Session,
    *,
    slug: str,
    max_chars: int = _CONTEXT_MAX_CHARS,
) -> dict[str, Any]:
    doc = repo.get_context_document(session, slug)
    if doc is None:
        return {"error": f"Unknown slug: {slug}", "slug": slug}
    max_chars = max(500, min(int(max_chars), _CONTEXT_MAX_CHARS))
    body = doc.body_markdown or ""
    truncated = len(body) > max_chars
    return {
        "slug": doc.slug,
        "title": doc.title,
        "body_markdown": body[:max_chars],
        "truncated": truncated,
    }


def list_releases(session: Session, *, limit: int = 12) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 30))
    releases = list(
        session.scalars(
            select(MusicRelease)
            .order_by(MusicRelease.release_date.desc().nulls_last())
            .limit(limit)
        )
    )
    return [
        {
            "id": r.id,
            "title": r.title,
            "release_date": r.release_date,
            "album_type": r.album_type,
        }
        for r in releases
    ]


def upsert_draft(
    session: Session,
    *,
    caption: str,
    title: str | None = None,
    hashtags: list[str] | None = None,
    platforms: list[str] | None = None,
    draft_id: int | None = None,
    thread_id: int | None = None,
) -> dict[str, Any]:
    if draft_id is not None:
        draft = session.get(ContentDraft, draft_id)
        if draft is None:
            return {"error": f"Draft {draft_id} not found"}
        draft.caption = caption
        if title is not None:
            draft.title = title
        if hashtags is not None:
            draft.hashtags = hashtags
        if platforms is not None:
            draft.platform_targets = platforms
        if thread_id is not None and draft.thread_id is None:
            draft.thread_id = thread_id
        session.flush()
    else:
        draft = repo.create_draft(
            session,
            title=(title or caption[:80] or "Untitled draft"),
            caption=caption,
            hashtags=hashtags or [],
            platform_targets=platforms or ["instagram"],
            status="draft",
            thread_id=thread_id,
            agent_notes="Saved via agent upsert_draft; no publish.",
            meta={"source": "agent_tool"},
        )
    return {
        "id": draft.id,
        "title": draft.title,
        "caption": draft.caption,
        "hashtags": draft.hashtags,
        "platforms": draft.platform_targets,
        "status": draft.status,
    }


def get_draft(session: Session, *, draft_id: int) -> dict[str, Any]:
    draft = session.get(ContentDraft, draft_id)
    if draft is None:
        return {"error": f"Draft {draft_id} not found"}
    return {
        "id": draft.id,
        "title": draft.title,
        "caption": draft.caption,
        "hashtags": draft.hashtags,
        "platforms": draft.platform_targets,
        "status": draft.status,
    }


def compact_identity_blurb(session: Session) -> str:
    """Short grounding for the system prompt — not a full context dump."""
    profile = repo.get_setting(session, "profile") or {}
    name = (profile.get("display_name") or "").strip()
    accounts = list(session.scalars(select(PlatformAccount)))
    connected = [
        a.source
        for a in accounts
        if a.status == "connected" and a.external_id
    ]
    if not name:
        for a in accounts:
            candidate = (a.display_name or a.username or "").strip()
            if candidate and a.status == "connected":
                name = candidate
                break
    name = name or "Artist"
    platforms = ", ".join(connected) if connected else "none connected yet"
    return f"Artist: {name}. Connected platforms: {platforms}."


class ToolContext:
    """Per-turn execution context (thread id for draft linkage)."""

    def __init__(self, session: Session, *, thread_id: int | None = None) -> None:
        self.session = session
        self.thread_id = thread_id
        self.draft_updates: list[dict[str, Any]] = []


def execute_tool(
    session: Session,
    name: str,
    arguments: dict[str, Any],
    *,
    ctx: ToolContext | None = None,
) -> str:
    """Run a named tool and return a JSON string for the model."""
    thread_id = ctx.thread_id if ctx else None
    try:
        if name == "query_posts":
            rows = query_posts(
                session,
                source=arguments.get("source"),
                order_by=arguments.get("order_by") or "like_count",
                order=arguments.get("order") or "desc",
                limit=arguments.get("limit") or 5,
            )
            return json.dumps({"posts": rows, "count": len(rows)}, ensure_ascii=False)
        if name == "query_comments":
            rows = query_comments(
                session,
                source=arguments.get("source"),
                post_external_id=arguments.get("post_external_id"),
                sentiment=arguments.get("sentiment"),
                theme=arguments.get("theme"),
                limit=arguments.get("limit") or 10,
            )
            return json.dumps({"comments": rows, "count": len(rows)}, ensure_ascii=False)
        if name == "list_context_docs":
            return json.dumps({"docs": list_context_docs(session)}, ensure_ascii=False)
        if name == "get_context_doc":
            slug = arguments.get("slug")
            if not slug:
                raise ValueError("slug is required")
            return json.dumps(
                get_context_doc(
                    session,
                    slug=str(slug),
                    max_chars=arguments.get("max_chars") or _CONTEXT_MAX_CHARS,
                ),
                ensure_ascii=False,
            )
        if name == "list_releases":
            return json.dumps(
                {"releases": list_releases(session, limit=arguments.get("limit") or 12)},
                ensure_ascii=False,
            )
        if name == "upsert_draft":
            caption = arguments.get("caption")
            if not caption:
                raise ValueError("caption is required")
            result = upsert_draft(
                session,
                caption=str(caption),
                title=arguments.get("title"),
                hashtags=arguments.get("hashtags"),
                platforms=arguments.get("platforms"),
                draft_id=arguments.get("draft_id"),
                thread_id=thread_id,
            )
            if ctx is not None and "id" in result:
                ctx.draft_updates.append(result)
            return json.dumps(result, ensure_ascii=False)
        if name == "get_draft":
            draft_id = arguments.get("draft_id")
            if draft_id is None:
                raise ValueError("draft_id is required")
            return json.dumps(get_draft(session, draft_id=int(draft_id)), ensure_ascii=False)
        return json.dumps({"error": f"Unknown tool: {name}"})
    except (TypeError, ValueError) as exc:
        return json.dumps({"error": str(exc)})


def openai_tool_defs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in AGENT_TOOLS
    ]


def anthropic_tool_defs() -> list[dict[str, Any]]:
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool["parameters"],
        }
        for tool in AGENT_TOOLS
    ]
