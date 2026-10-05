"""API route aggregators and handlers."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import AdapterError, CredentialError
from app.agent.chat import iter_turn_events, run_turn, thread_to_dict
from app.agent.content import export_package, generate_content_draft
from app.config import get_settings
from app.context.generator import regenerate_all_context
from app.db import get_db, get_session_factory
from app.db import repository as repo
from app.db.models import (
    ContentDraft,
    ContextDocument,
    MediaAsset,
    MusicArtist,
    MusicRelease,
    PlatformAccount,
    Post,
    SyncRun,
)
from app.media.pipeline import adapt_all_presets
from app.sync.service import SyncService

router = APIRouter()


# ----- Health already mounted separately -----


class SyncRequest(BaseModel):
    sources: list[str] | None = None


@router.post("/sync/refresh")
def sync_refresh(body: SyncRequest | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    settings = get_settings()
    sources = body.sources if body else None
    # Keep tests synchronous; live/dev use a background thread so the HTTP
    # request does not time out on multi-page Instagram (etc.) pulls.
    if settings.environment == "test":
        service = SyncService(db, context_regen=regenerate_all_context)
        return service.run(sources=sources, trigger="manual")

    from app.sync.service import begin_manual_sync

    return begin_manual_sync(db, sources=sources)


@router.get("/sync/status")
def sync_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    # Drop leftover fixture identities immediately when running live.
    repo.purge_stale_live_identities(db)
    accounts = list(db.scalars(select(PlatformAccount)))
    latest = db.scalar(select(SyncRun).order_by(SyncRun.id.desc()).limit(1))
    return {
        "accounts": [
            {
                "source": a.source,
                "status": a.status,
                "last_synced_at": a.last_synced_at,
                "last_error": a.last_error,
                "external_id": a.external_id,
                "display_name": a.display_name,
                "username": a.username,
                "no_data": a.no_data,
                "meta": a.meta,
            }
            for a in accounts
        ],
        "latest_run": (
            {
                "id": latest.id,
                "status": latest.status,
                "trigger": latest.trigger,
                "started_at": latest.started_at,
                "finished_at": latest.finished_at,
                "per_source": latest.per_source,
            }
            if latest
            else None
        ),
    }


@router.get("/sync/history")
def sync_history(db: Session = Depends(get_db), limit: int = Query(20, le=100)) -> list[dict[str, Any]]:
    runs = list(db.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(limit)))
    return [
        {
            "id": r.id,
            "status": r.status,
            "trigger": r.trigger,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "per_source": r.per_source,
            "error_summary": r.error_summary,
        }
        for r in runs
    ]


class IdentityConfirm(BaseModel):
    source: str
    external_id: str
    display_name: str | None = None


@router.get("/music/search")
def music_search(source: str, q: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    service = SyncService(db)
    adapter = service.build_adapter(source)
    if adapter is None:
        raise HTTPException(400, "Unknown source")
    try:
        results = adapter.search_identity(q)
    except CredentialError as exc:
        raise HTTPException(503, str(exc)) from exc
    except AdapterError as exc:
        raise HTTPException(502, str(exc)) from exc
    return [r.model_dump() for r in results]


@router.post("/music/confirm")
def music_confirm(body: IdentityConfirm, db: Session = Depends(get_db)) -> dict[str, Any]:
    account = repo.upsert_platform_account(
        db,
        source=body.source,
        external_id=body.external_id,
        display_name=body.display_name,
        status="connected",
        meta={"from_fixtures": False},
    )
    artist = repo.resolve_music_artist(
        db,
        name=body.display_name or body.external_id,
        source=body.source,
        external_id=body.external_id,
    )
    # Keep settings profile name in sync when confirming an identity
    if body.display_name:
        profile = repo.get_setting(db, "profile") or {}
        if not profile.get("display_name"):
            repo.set_setting(db, "profile", {**profile, "display_name": body.display_name})
    db.commit()
    return {
        "ok": True,
        "account_id": account.id,
        "source": account.source,
        "external_id": account.external_id,
        "artist_id": artist.id,
        "artist_name": artist.name,
    }


@router.get("/library/music")
def library_music(db: Session = Depends(get_db)) -> dict[str, Any]:
    artists = list(db.scalars(select(MusicArtist)))
    releases = list(db.scalars(select(MusicRelease)))
    return {
        "artists": [
            {
                "id": a.id,
                "name": a.name,
                "spotify_id": a.spotify_id,
                "soundcloud_id": a.soundcloud_id,
                "deezer_id": a.deezer_id,
                "genres": a.genres,
                "image_url": a.image_url,
                "follower_counts": a.follower_counts,
            }
            for a in artists
        ],
        "releases": [
            {
                "id": r.id,
                "title": r.title,
                "release_date": r.release_date,
                "cover_url": r.cover_url,
                "source_ids": r.source_ids,
                "spotify_id": r.spotify_id,
                "soundcloud_id": r.soundcloud_id,
                "deezer_id": r.deezer_id,
            }
            for r in releases
        ],
    }


@router.get("/library/posts")
def library_posts(
    db: Session = Depends(get_db),
    source: str | None = None,
    limit: int = Query(50, le=200),
) -> list[dict[str, Any]]:
    stmt = select(Post).order_by(Post.posted_at.desc()).limit(limit)
    if source:
        stmt = select(Post).where(Post.source == source).order_by(Post.posted_at.desc()).limit(limit)
    posts = list(db.scalars(stmt))
    return [
        {
            "id": p.id,
            "source": p.source,
            "external_id": p.external_id,
            "caption": p.caption,
            "permalink": p.permalink,
            "posted_at": p.posted_at,
            "media_type": p.media_type,
            "like_count": p.like_count,
            "comment_count": p.comment_count,
            "view_count": p.view_count,
        }
        for p in posts
    ]


@router.get("/library/media")
def library_media(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    assets = list(db.scalars(select(MediaAsset).order_by(MediaAsset.id.desc())))
    return [
        {
            "id": a.id,
            "kind": a.kind,
            "filename": a.filename,
            "storage_path": a.storage_path,
            "format_preset": a.format_preset,
            "width": a.width,
            "height": a.height,
            "focal_point": a.focal_point,
            "crop_box": a.crop_box,
            "parent_id": a.parent_id,
        }
        for a in assets
    ]


@router.get("/context")
def list_context(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    docs = list(db.scalars(select(ContextDocument)))
    return [
        {
            "id": d.id,
            "slug": d.slug,
            "title": d.title,
            "body_markdown": d.body_markdown,
            "section_locks": d.section_locks,
            "front_matter": d.front_matter,
            "updated_at": d.updated_at,
        }
        for d in docs
    ]


@router.get("/context/{slug}")
def get_context(slug: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    doc = repo.get_context_document(db, slug)
    if not doc:
        raise HTTPException(404, "Not found")
    return {
        "id": doc.id,
        "slug": doc.slug,
        "title": doc.title,
        "body_markdown": doc.body_markdown,
        "section_locks": doc.section_locks,
        "front_matter": doc.front_matter,
    }


class ContextUpdate(BaseModel):
    body_markdown: str | None = None
    section_locks: dict[str, Any] | None = None
    title: str | None = None


@router.put("/context/{slug}")
def update_context(slug: str, body: ContextUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    doc = repo.get_context_document(db, slug)
    if not doc:
        doc = repo.upsert_context_document(db, slug=slug, title=body.title or slug, body_markdown=body.body_markdown or "")
    if body.body_markdown is not None:
        doc.body_markdown = body.body_markdown
    if body.section_locks is not None:
        doc.section_locks = body.section_locks
    if body.title is not None:
        doc.title = body.title
    db.commit()
    return {"ok": True, "slug": doc.slug}


@router.post("/context/regenerate")
def regen_context(db: Session = Depends(get_db)) -> dict[str, Any]:
    regenerate_all_context(db)
    db.commit()
    return {"ok": True}


class SettingsUpdate(BaseModel):
    artist_links: dict[str, str] | None = None
    display_name: str | None = None


@router.get("/settings")
def get_settings_api(db: Session = Depends(get_db)) -> dict[str, Any]:
    links = repo.get_setting(db, "artist_links") or {}
    profile = repo.get_setting(db, "profile") or {}
    settings = get_settings()
    return {
        "artist_links": links,
        "profile": profile,
        "platform_live": not settings.use_fixtures,
        "fixture_mode": settings.use_fixtures,
        "llm_live": bool(settings.llm_live),
    }


@router.put("/settings")
def put_settings(body: SettingsUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    if body.artist_links is not None:
        repo.set_setting(db, "artist_links", body.artist_links)
    if body.display_name is not None:
        repo.set_setting(db, "profile", {"display_name": body.display_name})
    db.commit()
    return {"ok": True}


class AgentRequest(BaseModel):
    prompt: str
    platforms: list[str] = Field(default_factory=lambda: ["instagram"])


class ThreadCreate(BaseModel):
    title: str | None = None


class ChatMessageRequest(BaseModel):
    content: str = Field(min_length=1)


@router.post("/studio/generate")
def studio_generate(body: AgentRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Compat one-shot generate (creates a thread under the hood)."""
    return generate_content_draft(db, prompt=body.prompt, platforms=body.platforms)


@router.get("/studio/threads")
def studio_list_threads(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    threads = repo.list_threads(db)
    return [thread_to_dict(t) for t in threads]


@router.post("/studio/threads")
def studio_create_thread(body: ThreadCreate | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    title = body.title if body else None
    thread = repo.create_thread(db, title=title)
    db.commit()
    return thread_to_dict(thread)


@router.get("/studio/threads/{thread_id}")
def studio_get_thread(thread_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    thread = repo.get_thread(db, thread_id)
    if thread is None:
        raise HTTPException(404, "Thread not found")
    # Ensure messages are loaded
    _ = thread.messages
    return thread_to_dict(thread, include_messages=True)


@router.post("/studio/threads/{thread_id}/messages")
def studio_post_message(
    thread_id: int,
    body: ChatMessageRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    thread = repo.get_thread(db, thread_id)
    if thread is None:
        raise HTTPException(404, "Thread not found")
    try:
        result = run_turn(db, thread, body.content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return result


@router.post("/studio/threads/{thread_id}/messages/stream")
def studio_post_message_stream(
    thread_id: int,
    body: ChatMessageRequest,
) -> StreamingResponse:
    # Dedicated session inside the generator — Depends(get_db) would close
    # before StreamingResponse iterates.
    def event_gen() -> Iterator[str]:
        session = get_session_factory()()
        try:
            thread = repo.get_thread(session, thread_id)
            if thread is None:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Thread not found'})}\n\n"
                return
            for event in iter_turn_events(session, thread, body.content):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001 — surface to client then end stream
            session.rollback()
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            session.close()

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/studio/drafts")
def studio_drafts(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    drafts = list(db.scalars(select(ContentDraft).order_by(ContentDraft.id.desc())))
    return [
        {
            "id": d.id,
            "title": d.title,
            "caption": d.caption,
            "hashtags": d.hashtags,
            "platforms": d.platform_targets,
            "status": d.status,
            "media_asset_ids": d.media_asset_ids,
            "prepared_assets": d.prepared_assets,
            "thread_id": d.thread_id,
        }
        for d in drafts
    ]


@router.get("/studio/drafts/{draft_id}/export")
def studio_export(draft_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return export_package(db, draft_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/media/upload")
async def media_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    settings = get_settings()
    root = Path(settings.media_root)
    originals = root / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "upload.jpg"
    dest = originals / filename
    content = await file.read()
    dest.write_bytes(content)
    asset = repo.create_media_asset(
        db,
        kind="original",
        filename=filename,
        storage_path=str(dest),
        mime_type=file.content_type,
    )
    db.commit()
    return {"id": asset.id, "filename": filename, "storage_path": str(dest)}

class AdaptRequest(BaseModel):
    media_id: int
    focal_point: dict[str, float] | None = None
    presets: list[str] | None = None


@router.post("/media/adapt")
def media_adapt(body: AdaptRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    asset = db.get(MediaAsset, body.media_id)
    if not asset:
        raise HTTPException(404, "Media not found")
    settings = get_settings()
    source = Path(asset.storage_path)
    if not source.exists():
        raise HTTPException(400, "Source file missing")
    out_dir = Path(settings.media_root) / "variants" / str(asset.id)
    results = adapt_all_presets(source, out_dir, focal_point=body.focal_point, presets=body.presets)
    variants = []
    for r in results:
        v = repo.create_media_asset(
            db,
            kind="variant",
            filename=r.path.name,
            storage_path=str(r.path),
            mime_type="image/jpeg",
            width=r.width,
            height=r.height,
            parent_id=asset.id,
            format_preset=r.format_preset,
            crop_box=r.crop_box,
            focal_point=r.focal_point,
        )
        variants.append({"id": v.id, "preset": r.format_preset, "path": str(r.path)})
    db.commit()
    return {"original_id": asset.id, "variants": variants}


@router.get("/quota/youtube")
def youtube_quota(db: Session = Depends(get_db)) -> dict[str, Any]:
    account = db.scalar(select(PlatformAccount).where(PlatformAccount.source == "youtube"))
    if not account:
        return {"used": 0, "limit": 10000, "remaining": 10000}
    return (account.meta or {}).get("quota") or {"used": 0, "limit": 10000, "remaining": 10000}
