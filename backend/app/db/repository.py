"""Repository / DAO helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AgentMessage,
    AgentThread,
    AppSetting,
    Comment,
    ContentDraft,
    ContextDocument,
    EncryptedToken,
    MediaAsset,
    MusicArtist,
    MusicRelease,
    MusicTrack,
    PlatformAccount,
    Post,
    SyncRun,
    TopicTag,
)
from app.security.tokens import decrypt_token, encrypt_token


def upsert_platform_account(
    session: Session,
    *,
    source: str,
    external_id: str | None = None,
    display_name: str | None = None,
    username: str | None = None,
    profile_url: str | None = None,
    avatar_url: str | None = None,
    status: str = "connected",
    meta: dict[str, Any] | None = None,
    no_data: bool = False,
) -> PlatformAccount:
    account = session.scalar(select(PlatformAccount).where(PlatformAccount.source == source))
    if account is None:
        account = PlatformAccount(source=source)
        session.add(account)
    if external_id is not None:
        account.external_id = external_id
    if display_name is not None:
        account.display_name = display_name
    if username is not None:
        account.username = username
    if profile_url is not None:
        account.profile_url = profile_url
    if avatar_url is not None:
        account.avatar_url = avatar_url
    account.status = status
    account.no_data = no_data
    if meta is not None:
        account.meta = meta
    session.flush()
    return account


def clear_platform_identity(
    session: Session,
    account: PlatformAccount,
    *,
    status: str = "needs_auth",
    last_error: str | None = None,
) -> PlatformAccount:
    """Wipe display/id fields so fixture leftovers never show in live mode."""
    account.external_id = None
    account.display_name = None
    account.username = None
    account.profile_url = None
    account.avatar_url = None
    account.status = status
    account.no_data = False
    account.meta = {}
    account.last_error = last_error
    session.flush()
    return account


# Platforms that need a stored OAuth token for a real live identity.
_OAUTH_IDENTITY_SOURCES = frozenset(
    {"soundcloud", "instagram", "facebook", "threads", "tiktok", "youtube"}
)
_MUSIC_SOURCES = frozenset({"spotify", "soundcloud", "deezer"})
_ALL_SYNC_SOURCES = (
    "spotify",
    "soundcloud",
    "deezer",
    "instagram",
    "facebook",
    "threads",
    "tiktok",
    "youtube",
)


_FIXTURE_POST_EXTERNAL_IDS: dict[str, frozenset[str]] = {
    "instagram": frozenset({"ig_media_1", "ig_media_2"}),
    "facebook": frozenset({"fb_p1"}),
    "threads": frozenset({"th_p1"}),
    "tiktok": frozenset({"tt_v1"}),
    "youtube": frozenset({"yt_v1", "yt_v2"}),
}


def delete_posts_for_source(session: Session, source: str) -> int:
    """Delete all posts for a source (comments/topic tags cascade)."""
    posts = list(session.scalars(select(Post).where(Post.source == source)))
    for post in posts:
        session.delete(post)
    session.flush()
    return len(posts)


def delete_posts_except(session: Session, source: str, keep_external_ids: set[str]) -> int:
    """Delete posts for source whose external_id is not in keep_external_ids."""
    posts = list(session.scalars(select(Post).where(Post.source == source)))
    deleted = 0
    for post in posts:
        if post.external_id not in keep_external_ids:
            session.delete(post)
            deleted += 1
    if deleted:
        session.flush()
    return deleted


def delete_known_fixture_posts(session: Session, source: str | None = None) -> int:
    """Delete posts matching known offline fixture external_ids."""
    sources = (source,) if source else tuple(_FIXTURE_POST_EXTERNAL_IDS)
    deleted = 0
    for src in sources:
        fixture_ids = _FIXTURE_POST_EXTERNAL_IDS.get(src)
        if not fixture_ids:
            continue
        posts = list(session.scalars(select(Post).where(Post.source == src)))
        for post in posts:
            if post.external_id in fixture_ids:
                session.delete(post)
                deleted += 1
    if deleted:
        session.flush()
    return deleted


def wipe_music_ids_for_source(session: Session, source: str) -> int:
    """Clear platform ids on catalog rows for a music source that is no longer live.

    Returns the number of fields cleared.
    """
    id_field = {"spotify": "spotify_id", "soundcloud": "soundcloud_id", "deezer": "deezer_id"}.get(
        source
    )
    if not id_field:
        return 0
    changed = 0
    for artist in list(session.scalars(select(MusicArtist))):
        if getattr(artist, id_field):
            setattr(artist, id_field, None)
            changed += 1
        counts = dict(artist.follower_counts or {})
        if source in counts:
            counts.pop(source, None)
            artist.follower_counts = counts
            changed += 1
    for release in list(session.scalars(select(MusicRelease))):
        if getattr(release, id_field):
            setattr(release, id_field, None)
            changed += 1
        ids = dict(release.source_ids or {})
        if source in ids:
            ids.pop(source, None)
            release.source_ids = ids
            changed += 1
    for track in list(session.scalars(select(MusicTrack))):
        if getattr(track, id_field):
            setattr(track, id_field, None)
            changed += 1
        ids = dict(track.source_ids or {})
        if source in ids:
            ids.pop(source, None)
            track.source_ids = ids
            changed += 1
    if changed:
        session.flush()
    return changed


def source_is_live_ready(session: Session, account: PlatformAccount | None) -> bool:
    """True when the account can serve real live data (not fixture leftovers)."""
    if account is None:
        return False
    meta = account.meta if isinstance(account.meta, dict) else {}
    if meta.get("from_fixtures"):
        return False
    if account.status != "connected":
        return False
    if account.source in _OAUTH_IDENTITY_SOURCES:
        return bool(load_account_token(session, account))
    # Spotify / Deezer: confirmed artist id is enough (public / client-credentials).
    return bool(account.external_id)


def purge_stale_live_identities(session: Session) -> int:
    """Clear fixture identities + synced posts/catalog when PLATFORM_LIVE is on.

    Returns the number of accounts/sources cleaned.
    """
    from app.config import get_settings

    if get_settings().use_fixtures:
        return 0

    cleared = 0
    content_wiped = False
    accounts = {a.source: a for a in session.scalars(select(PlatformAccount))}

    for source in _ALL_SYNC_SOURCES:
        account = accounts.get(source)
        live_ready = source_is_live_ready(session, account)

        if account is not None and not live_ready:
            meta = account.meta if isinstance(account.meta, dict) else {}
            from_fixtures = bool(meta.get("from_fixtures"))
            token = load_account_token(session, account) if account.id else None
            should_clear_identity = from_fixtures or (
                source in _OAUTH_IDENTITY_SOURCES
                and not token
                and bool(account.external_id or account.display_name or account.username)
            )
            # Also clear if still marked connected without credentials.
            if account.status == "connected" and not live_ready:
                should_clear_identity = True
            if should_clear_identity and (
                account.external_id or account.display_name or account.username or from_fixtures
            ):
                clear_platform_identity(
                    session,
                    account,
                    status="needs_auth",
                    last_error="Identity cleared: live mode requires a real connection",
                )
                cleared += 1

        if not live_ready:
            deleted = delete_posts_for_source(session, source)
            if deleted:
                content_wiped = True
                cleared += 1
            if source in _MUSIC_SOURCES:
                if wipe_music_ids_for_source(session, source):
                    content_wiped = True
                    cleared += 1
        else:
            # Connected live accounts: drop known fixture leftover rows immediately.
            if delete_known_fixture_posts(session, source):
                content_wiped = True
                cleared += 1

    if content_wiped or cleared:
        session.commit()
        try:
            from app.context.generator import regenerate_all_context

            regenerate_all_context(session)
            session.commit()
        except Exception:
            # Context regen is best-effort; identity/content wipe already committed.
            session.rollback()
    return cleared


def store_account_token(
    session: Session,
    account: PlatformAccount,
    plaintext_token: str,
    *,
    token_type: str = "oauth",
    expires_at: datetime | None = None,
    scopes: str | None = None,
) -> EncryptedToken:
    ciphertext = encrypt_token(plaintext_token)
    token = session.scalar(
        select(EncryptedToken).where(EncryptedToken.account_id == account.id)
    )
    if token is None:
        token = EncryptedToken(account_id=account.id, ciphertext=ciphertext)
        session.add(token)
    else:
        token.ciphertext = ciphertext
    token.token_type = token_type
    token.expires_at = expires_at
    token.scopes = scopes
    session.flush()
    return token


def load_account_token(session: Session, account: PlatformAccount) -> str | None:
    token = session.scalar(
        select(EncryptedToken).where(EncryptedToken.account_id == account.id)
    )
    if token is None:
        return None
    return decrypt_token(token.ciphertext)


def upsert_post(
    session: Session,
    *,
    source: str,
    external_id: str,
    permalink: str | None = None,
    caption: str | None = None,
    posted_at: datetime | None = None,
    media_type: str | None = None,
    like_count: int | None = None,
    comment_count: int | None = None,
    view_count: int | None = None,
    raw: dict[str, Any] | None = None,
) -> Post:
    post = session.scalar(
        select(Post).where(Post.source == source, Post.external_id == external_id)
    )
    if post is None:
        post = Post(source=source, external_id=external_id)
        session.add(post)
    post.permalink = permalink
    post.caption = caption
    post.posted_at = posted_at
    post.media_type = media_type
    post.like_count = like_count
    post.comment_count = comment_count
    post.view_count = view_count
    post.raw = raw
    session.flush()
    return post


def add_comment(
    session: Session,
    post: Post,
    *,
    source: str,
    external_id: str,
    author_name: str | None = None,
    body: str | None = None,
    commented_at: datetime | None = None,
    sentiment: str | None = None,
    theme: str | None = None,
    raw: dict[str, Any] | None = None,
) -> Comment:
    existing = session.scalar(
        select(Comment).where(Comment.source == source, Comment.external_id == external_id)
    )
    if existing:
        existing.body = body
        existing.sentiment = sentiment
        existing.theme = theme
        session.flush()
        return existing
    comment = Comment(
        post_id=post.id,
        source=source,
        external_id=external_id,
        author_name=author_name,
        body=body,
        commented_at=commented_at,
        sentiment=sentiment,
        theme=theme,
        raw=raw,
    )
    session.add(comment)
    session.flush()
    return comment


def create_media_asset(
    session: Session,
    *,
    kind: str,
    filename: str,
    storage_path: str,
    mime_type: str | None = None,
    width: int | None = None,
    height: int | None = None,
    parent_id: int | None = None,
    source_post_id: int | None = None,
    format_preset: str | None = None,
    crop_box: dict[str, Any] | None = None,
    focal_point: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> MediaAsset:
    asset = MediaAsset(
        kind=kind,
        filename=filename,
        storage_path=storage_path,
        mime_type=mime_type,
        width=width,
        height=height,
        parent_id=parent_id,
        source_post_id=source_post_id,
        format_preset=format_preset,
        crop_box=crop_box,
        focal_point=focal_point,
        meta=meta,
    )
    session.add(asset)
    session.flush()
    return asset


_MUSIC_ARTIST_ID_FIELDS: dict[str, str] = {
    "spotify": "spotify_id",
    "soundcloud": "soundcloud_id",
    "deezer": "deezer_id",
}


def resolve_music_artist(
    session: Session,
    *,
    name: str,
    source: str | None = None,
    external_id: str | None = None,
) -> MusicArtist:
    """Find artist by platform id first, then name; create if missing."""
    id_field = _MUSIC_ARTIST_ID_FIELDS.get(source or "")
    if external_id and id_field:
        artist = session.scalar(
            select(MusicArtist).where(getattr(MusicArtist, id_field) == external_id)
        )
        if artist is not None:
            if name and artist.name != name:
                artist.name = name
            return artist

    artist = session.scalar(select(MusicArtist).where(MusicArtist.name == name))
    if artist is None:
        artist = MusicArtist(name=name or "Artist")
        session.add(artist)
        session.flush()

    if external_id and id_field:
        current = getattr(artist, id_field)
        if current is None:
            setattr(artist, id_field, external_id)
        elif current != external_id:
            owner = session.scalar(
                select(MusicArtist).where(getattr(MusicArtist, id_field) == external_id)
            )
            if owner is not None:
                return owner

    return artist


def get_or_create_music_artist(session: Session, name: str) -> MusicArtist:
    return resolve_music_artist(session, name=name)


def upsert_music_release(
    session: Session,
    *,
    title: str,
    normalized_title: str,
    release_date: str | None = None,
    artist_id: int | None = None,
    album_type: str | None = None,
    cover_url: str | None = None,
    genres: list[Any] | None = None,
    source: str | None = None,
    source_id: str | None = None,
) -> MusicRelease:
    release = session.scalar(
        select(MusicRelease).where(
            MusicRelease.normalized_title == normalized_title,
            MusicRelease.release_date == release_date,
        )
    )
    if release is None:
        release = MusicRelease(
            title=title,
            normalized_title=normalized_title,
            release_date=release_date,
            artist_id=artist_id,
            source_ids={},
        )
        session.add(release)
    else:
        # Prefer incoming title if empty
        if not release.title:
            release.title = title
    if album_type:
        release.album_type = album_type
    if cover_url:
        release.cover_url = cover_url
    if genres:
        release.genres = genres
    if source and source_id:
        ids = dict(release.source_ids or {})
        ids[source] = source_id
        release.source_ids = ids
        if source == "spotify":
            release.spotify_id = source_id
        elif source == "soundcloud":
            release.soundcloud_id = source_id
        elif source == "deezer":
            release.deezer_id = source_id
    session.flush()
    return release


def upsert_music_track(
    session: Session,
    *,
    title: str,
    normalized_title: str,
    release_id: int | None = None,
    artist_id: int | None = None,
    duration_ms: int | None = None,
    source: str | None = None,
    source_id: str | None = None,
) -> MusicTrack:
    track = session.scalar(
        select(MusicTrack).where(
            MusicTrack.normalized_title == normalized_title,
            MusicTrack.release_id == release_id,
        )
    )
    if track is None:
        track = MusicTrack(
            title=title,
            normalized_title=normalized_title,
            release_id=release_id,
            artist_id=artist_id,
            source_ids={},
        )
        session.add(track)
    if duration_ms is not None:
        track.duration_ms = duration_ms
    if source and source_id:
        ids = dict(track.source_ids or {})
        ids[source] = source_id
        track.source_ids = ids
        if source == "spotify":
            track.spotify_id = source_id
        elif source == "soundcloud":
            track.soundcloud_id = source_id
        elif source == "deezer":
            track.deezer_id = source_id
    session.flush()
    return track


def ensure_topic(session: Session, slug: str, label: str) -> TopicTag:
    tag = session.scalar(select(TopicTag).where(TopicTag.slug == slug))
    if tag is None:
        tag = TopicTag(slug=slug, label=label)
        session.add(tag)
        session.flush()
    return tag


def get_context_document(session: Session, slug: str) -> ContextDocument | None:
    return session.scalar(select(ContextDocument).where(ContextDocument.slug == slug))


def upsert_context_document(
    session: Session,
    *,
    slug: str,
    title: str,
    body_markdown: str,
    front_matter: dict[str, Any] | None = None,
    section_locks: dict[str, Any] | None = None,
) -> ContextDocument:
    doc = get_context_document(session, slug)
    if doc is None:
        doc = ContextDocument(slug=slug, title=title, body_markdown=body_markdown)
        session.add(doc)
    else:
        locks = doc.section_locks or {}
        # Preserve locked sections: naive whole-body replace only if unlocked
        if not locks:
            doc.body_markdown = body_markdown
        doc.title = title
    if front_matter is not None:
        doc.front_matter = front_matter
    if section_locks is not None:
        doc.section_locks = section_locks
    session.flush()
    return doc


def create_sync_run(session: Session, trigger: str = "manual") -> SyncRun:
    run = SyncRun(
        status="running",
        trigger=trigger,
        started_at=datetime.now(timezone.utc),
        per_source={},
    )
    session.add(run)
    session.flush()
    return run


def finish_sync_run(
    session: Session,
    run: SyncRun,
    *,
    status: str,
    per_source: dict[str, Any] | None = None,
    error_summary: str | None = None,
) -> SyncRun:
    run.status = status
    run.finished_at = datetime.now(timezone.utc)
    if per_source is not None:
        run.per_source = per_source
    run.error_summary = error_summary
    session.flush()
    return run


def get_setting(session: Session, key: str) -> dict[str, Any] | None:
    row = session.scalar(select(AppSetting).where(AppSetting.key == key))
    return row.value if row else None


def set_setting(session: Session, key: str, value: dict[str, Any]) -> AppSetting:
    row = session.scalar(select(AppSetting).where(AppSetting.key == key))
    if row is None:
        row = AppSetting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    session.flush()
    return row


def create_draft(session: Session, **kwargs: Any) -> ContentDraft:
    draft = ContentDraft(**kwargs)
    session.add(draft)
    session.flush()
    return draft


def create_thread(session: Session, *, title: str | None = None) -> AgentThread:
    thread = AgentThread(title=title or "Studio chat", status="active", meta={})
    session.add(thread)
    session.flush()
    return thread


def get_thread(session: Session, thread_id: int) -> AgentThread | None:
    return session.get(AgentThread, thread_id)


def list_threads(session: Session, *, limit: int = 50) -> list[AgentThread]:
    return list(
        session.scalars(
            select(AgentThread).order_by(AgentThread.id.desc()).limit(limit)
        )
    )


def add_message(
    session: Session,
    thread: AgentThread,
    *,
    role: str,
    content: str | None = None,
    tool_name: str | None = None,
    tool_call_id: str | None = None,
    tool_calls: list[Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> AgentMessage:
    msg = AgentMessage(
        thread_id=thread.id,
        role=role,
        content=content,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        tool_calls=tool_calls,
        meta=meta,
    )
    session.add(msg)
    session.flush()
    return msg


def list_messages(session: Session, thread_id: int) -> list[AgentMessage]:
    return list(
        session.scalars(
            select(AgentMessage)
            .where(AgentMessage.thread_id == thread_id)
            .order_by(AgentMessage.id.asc())
        )
    )