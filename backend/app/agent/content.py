"""Content agent helpers — draft export + one-shot compat wrapper."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agent.chat import run_turn
from app.db import repository as repo
from app.db.models import ContentDraft


def generate_content_draft(
    session: Session,
    *,
    prompt: str,
    platforms: list[str] | None = None,
) -> dict[str, Any]:
    """Compat: one-shot generate via a fresh interactive thread turn."""
    platforms = platforms or ["instagram"]
    thread = repo.create_thread(session, title=prompt[:80] or "Studio chat")
    # Hint platforms in the user message so the agent can target drafts
    text = prompt.strip()
    if platforms:
        text = f"{text}\n\n(Target platforms: {', '.join(platforms)})"
    result = run_turn(session, thread, text)
    draft = result["drafts"][0] if result["drafts"] else None
    if draft is None:
        # Ensure callers still get a draft row for older UI paths
        created = repo.create_draft(
            session,
            title=prompt[:80] or "Untitled draft",
            platform_targets=platforms,
            caption=result["content"],
            hashtags=["#music", "#newmusic"],
            status="draft",
            thread_id=thread.id,
            agent_notes="Compat generate; no publish.",
            meta={"fixture": True, "source": "compat_generate"},
        )
        session.commit()
        draft = {
            "id": created.id,
            "caption": created.caption,
            "hashtags": created.hashtags,
            "platforms": created.platform_targets,
            "status": created.status,
        }
    return {
        "id": draft["id"],
        "caption": draft.get("caption") or result["content"],
        "hashtags": draft.get("hashtags") or [],
        "platforms": draft.get("platforms") or platforms,
        "status": draft.get("status") or "draft",
        "thread_id": thread.id,
        "reply": result["content"],
    }


def export_package(session: Session, draft_id: int) -> dict[str, Any]:
    draft = session.get(ContentDraft, draft_id)
    if draft is None:
        raise ValueError("Draft not found")
    return {
        "caption": draft.caption,
        "hashtags": draft.hashtags,
        "platforms": draft.platform_targets,
        "media_asset_ids": draft.media_asset_ids or [],
        "prepared_assets": draft.prepared_assets or {},
        "note": "Export for manual publishing outside ArtistAssist. Not published.",
    }
