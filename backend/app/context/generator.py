"""Artist context markdown generation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import repository as repo
from app.db.models import Comment, MusicArtist, MusicRelease, MusicTrack, PlatformAccount, Post

_SOURCE_ID_FIELDS = {
    "spotify": "spotify_id",
    "soundcloud": "soundcloud_id",
    "deezer": "deezer_id",
}

# Prefer social display names for identity; music catalogs follow confirmed music accounts.
_NAME_SOURCE_PRIORITY = (
    "instagram",
    "facebook",
    "threads",
    "tiktok",
    "youtube",
    "deezer",
    "spotify",
    "soundcloud",
)
_MUSIC_SOURCES = ("spotify", "soundcloud", "deezer")
_PLATFORM_SOURCES = (
    "spotify",
    "instagram",
    "facebook",
    "threads",
    "tiktok",
    "youtube",
    "soundcloud",
    "deezer",
)


def _is_configured(account: PlatformAccount | None) -> bool:
    """True when the platform has a real connected identity — not fixture placeholders."""
    if account is None:
        return False
    if account.status != "connected":
        return False
    return bool(account.external_id)


def _configured_sources(accounts: list[PlatformAccount]) -> set[str]:
    return {a.source for a in accounts if _is_configured(a)}


def _section(title: str, body: str, locks: dict[str, Any], slug: str) -> str:
    if locks.get(slug):
        return f"<!-- locked:{slug} -->\n"
    return f"## {title}\n\n{body.strip()}\n"


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "unknown date"
    if value.tzinfo is None:
        return value.isoformat(timespec="seconds")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _fmt_count(label: str, value: int | None) -> str | None:
    if value is None:
        return None
    return f"{label}={value}"


def _post_stats_line(post: Post) -> str:
    parts = [
        p
        for p in (
            _fmt_count("likes", post.like_count),
            _fmt_count("comments", post.comment_count),
            _fmt_count("views", post.view_count),
        )
        if p
    ]
    return ", ".join(parts) if parts else "no engagement counts"


def _extra_raw_metrics(raw: dict[str, Any] | None) -> list[str]:
    """Surface common platform-specific counters from raw payloads when present."""
    if not raw:
        return []
    keys = (
        ("share_count", "shares"),
        ("shares", "shares"),
        ("save_count", "saves"),
        ("saves", "saves"),
        ("play_count", "plays"),
        ("plays", "plays"),
        ("reach", "reach"),
        ("impressions", "impressions"),
        ("favoriteCount", "favorites"),
        ("repost_count", "reposts"),
        ("quote_count", "quotes"),
    )
    out: list[str] = []
    seen: set[str] = set()
    for key, label in keys:
        if key not in raw or label in seen:
            continue
        value = raw.get(key)
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)):
            out.append(f"{label}={int(value)}")
            seen.add(label)
        elif isinstance(value, str) and value.isdigit():
            out.append(f"{label}={int(value)}")
            seen.add(label)
    return out


def _format_comment(comment: Comment) -> str:
    author = (comment.author_name or "unknown").strip() or "unknown"
    when = _fmt_dt(comment.commented_at)
    body = (comment.body or "").strip() or "(empty)"
    extras: list[str] = []
    if comment.sentiment:
        extras.append(f"sentiment={comment.sentiment}")
    if comment.theme:
        extras.append(f"theme={comment.theme}")
    meta = f" ({', '.join(extras)})" if extras else ""
    return f"  - @{author} ({when}){meta}: {body}"


def _format_post_block(
    post: Post,
    *,
    include_source: bool = False,
    include_comments: bool = True,
    caption_limit: int | None = None,
) -> str:
    header_bits = []
    if include_source:
        header_bits.append(f"[{post.source}]")
    header_bits.append(_fmt_dt(post.posted_at))
    if post.media_type:
        header_bits.append(post.media_type)
    header = " · ".join(header_bits)

    caption = (post.caption or "").strip() or "(no caption)"
    if caption_limit is not None and len(caption) > caption_limit:
        caption = caption[:caption_limit].rstrip() + "…"

    lines = [
        f"### {header}",
        f"- id: `{post.external_id}`",
        f"- stats: {_post_stats_line(post)}",
    ]
    extra = _extra_raw_metrics(post.raw if isinstance(post.raw, dict) else None)
    if extra:
        lines.append(f"- other metrics: {', '.join(extra)}")
    if post.permalink:
        lines.append(f"- permalink: {post.permalink}")
    lines.append(f"- caption: {caption}")

    if include_comments:
        comments = sorted(
            post.comments,
            key=lambda c: (
                c.commented_at is None,
                c.commented_at or datetime.min.replace(tzinfo=timezone.utc),
            ),
        )
        stored = len(comments)
        reported = post.comment_count
        if comments:
            count_note = f"{stored} stored"
            if reported is not None:
                count_note += f", {reported} reported"
            lines.append(f"- comments ({count_note}):")
            lines.extend(_format_comment(c) for c in comments)
        elif reported:
            lines.append(f"- comments: none stored ({reported} reported by platform)")
        else:
            lines.append("- comments: none")
    return "\n".join(lines)


def _engagement_summary(posts: list[Post]) -> str:
    if not posts:
        return "No posts synced."
    likes = [p.like_count for p in posts if p.like_count is not None]
    comments = [p.comment_count for p in posts if p.comment_count is not None]
    views = [p.view_count for p in posts if p.view_count is not None]
    bits = [f"{len(posts)} posts"]
    if likes:
        bits.append(f"likes total={sum(likes)} avg={sum(likes) // len(likes)} max={max(likes)}")
    if comments:
        bits.append(
            f"comments total={sum(comments)} avg={sum(comments) // len(comments)} max={max(comments)}"
        )
    if views:
        bits.append(f"views total={sum(views)} avg={sum(views) // len(views)} max={max(views)}")
    return "; ".join(bits)


def _load_posts(session: Session, *, source: str | None = None) -> list[Post]:
    stmt = (
        select(Post)
        .options(selectinload(Post.comments))
        .order_by(Post.posted_at.desc().nulls_last())
    )
    if source is not None:
        stmt = stmt.where(Post.source == source)
    return list(session.scalars(stmt))


def _display_name_from_accounts(accounts: list[PlatformAccount]) -> str | None:
    by_source = {a.source: a for a in accounts}
    for source in _NAME_SOURCE_PRIORITY:
        account = by_source.get(source)
        if not account or account.status not in {"connected", "needs_auth"}:
            continue
        name = (account.display_name or account.username or "").strip()
        if name:
            return name
    return None


def resolve_primary_music_artist(
    session: Session, accounts: list[PlatformAccount] | None = None
) -> MusicArtist | None:
    """Pick the music artist that matches the current identity, not stale fixture rows."""
    accounts = accounts if accounts is not None else list(session.scalars(select(PlatformAccount)))
    # Without a configured music platform, never surface fixture/catalog rows.
    if not any(_is_configured(a) for a in accounts if a.source in _MUSIC_SOURCES):
        return None
    by_source = {a.source: a for a in accounts}
    display = _display_name_from_accounts(accounts)
    profile = repo.get_setting(session, "profile") or {}
    configured = (profile.get("display_name") or "").strip()
    identity = configured or display

    if identity:
        artist = session.scalar(select(MusicArtist).where(MusicArtist.name == identity))
        if artist is not None:
            return artist

    for source in _MUSIC_SOURCES:
        account = by_source.get(source)
        if not _is_configured(account):
            continue
        assert account is not None
        # Skip leftover fixture accounts that don't match the current social identity
        account_name = (account.display_name or account.username or "").strip()
        if identity and account_name and account_name.casefold() != identity.casefold():
            continue
        id_field = {
            "spotify": "spotify_id",
            "soundcloud": "soundcloud_id",
            "deezer": "deezer_id",
        }[source]
        artist = session.scalar(
            select(MusicArtist).where(getattr(MusicArtist, id_field) == account.external_id)
        )
        if artist is not None:
            return artist

    # Do not fall back to an arbitrary MusicArtist row — that resurrects stale fixture ids.
    return None


def resolve_artist_display_name(
    session: Session, accounts: list[PlatformAccount] | None = None
) -> str:
    profile = repo.get_setting(session, "profile") or {}
    configured = (profile.get("display_name") or "").strip()
    if configured:
        return configured

    accounts = accounts if accounts is not None else list(session.scalars(select(PlatformAccount)))
    from_accounts = _display_name_from_accounts(accounts)
    if from_accounts:
        return from_accounts

    artist = resolve_primary_music_artist(session, accounts)
    if artist and artist.name:
        return artist.name
    return "Artist"


def generate_artist_profile(session: Session) -> str:
    accounts = list(session.scalars(select(PlatformAccount)))
    artist = resolve_primary_music_artist(session, accounts)
    name = resolve_artist_display_name(session, accounts)

    if artist is not None:
        releases = list(
            session.scalars(
                select(MusicRelease)
                .where(MusicRelease.artist_id == artist.id)
                .order_by(MusicRelease.release_date.desc().nulls_last())
                .limit(12)
            )
        )
        genres = ", ".join((artist.genres or [])[:6])
    else:
        releases = []
        genres = ""

    # Profile stays a grounding overview; full captions+comments live in platform_*.md.
    # Only include data from configured platforms — never leftover fixture rows.
    configured = _configured_sources(accounts)
    posts = [p for p in _load_posts(session) if p.source in configured]

    locks: dict[str, Any] = {}
    existing = repo.get_context_document(session, "artist_profile")
    if existing and existing.section_locks:
        locks = existing.section_locks

    parts = [
        f"---\nname: {name}\ngenerated_at: {datetime.now(timezone.utc).isoformat()}\n---\n",
    ]
    parts.append(
        _section(
            "Identity",
            f"**{name}**\n\nGenres: {genres or 'unknown'}\n",
            locks,
            "identity",
        )
    )
    platform_lines = []
    for a in accounts:
        if _is_configured(a):
            platform_lines.append(f"- {a.source}: @{a.username or a.display_name or a.external_id}")
    if platform_lines:
        parts.append(_section("Platforms", "\n".join(platform_lines), locks, "platforms"))
    if releases:
        release_lines = [f"- {r.title} ({r.release_date or 'n.d.'})" for r in releases]
        parts.append(_section("Catalog", "\n".join(release_lines), locks, "catalog"))

    if posts:
        post_body_parts = [
            f"Engagement overview: {_engagement_summary(posts)}",
            "Full captions and comments are in each `platform_<name>` document.",
            "",
        ]
        post_body_parts.extend(
            _format_post_block(
                p,
                include_source=True,
                include_comments=True,
                caption_limit=280,
            )
            for p in posts
        )
        parts.append(_section("Posts", "\n".join(post_body_parts), locks, "recent_posts"))
    parts.append(
        _section(
            "Tone of voice",
            "Warm, concise, musician-first. Prefer concrete release facts over hype.",
            locks,
            "tone",
        )
    )
    return "\n".join(p for p in parts if p.strip())


def _fmt_duration(ms: int | None) -> str | None:
    if ms is None or ms < 0:
        return None
    total_sec = ms // 1000
    minutes, seconds = divmod(total_sec, 60)
    return f"{minutes}:{seconds:02d}"


def _release_has_source(release: MusicRelease, source: str) -> bool:
    id_field = _SOURCE_ID_FIELDS.get(source)
    if id_field and getattr(release, id_field, None):
        return True
    source_ids = release.source_ids if isinstance(release.source_ids, dict) else {}
    return source in source_ids


def _track_has_source(track: MusicTrack, source: str) -> bool:
    id_field = _SOURCE_ID_FIELDS.get(source)
    if id_field and getattr(track, id_field, None):
        return True
    source_ids = track.source_ids if isinstance(track.source_ids, dict) else {}
    return source in source_ids


def _resolve_music_artist_for_source(
    session: Session, source: str, account: PlatformAccount | None
) -> MusicArtist | None:
    if not _is_configured(account):
        return None
    assert account is not None
    id_field = _SOURCE_ID_FIELDS.get(source)
    if account.external_id and id_field:
        artist = session.scalar(
            select(MusicArtist).where(getattr(MusicArtist, id_field) == account.external_id)
        )
        if artist is not None:
            return artist
    return resolve_primary_music_artist(session)


def _load_music_releases(session: Session, *, source: str, artist: MusicArtist | None) -> list[MusicRelease]:
    if artist is None:
        # No confirmed artist for this source — do not surface unrelated fixture rows.
        return []
    stmt = (
        select(MusicRelease)
        .options(selectinload(MusicRelease.tracks))
        .where(MusicRelease.artist_id == artist.id)
        .order_by(MusicRelease.release_date.desc().nulls_last())
    )
    releases = list(session.scalars(stmt))
    sourced = [r for r in releases if _release_has_source(r, source)]
    return sourced


def _format_release_block(release: MusicRelease, *, source: str) -> str:
    header_bits = [release.title]
    if release.release_date:
        header_bits.append(release.release_date)
    if release.album_type:
        header_bits.append(release.album_type)
    lines = [f"### {' · '.join(header_bits)}"]

    id_field = _SOURCE_ID_FIELDS.get(source)
    external_id = getattr(release, id_field, None) if id_field else None
    if not external_id and isinstance(release.source_ids, dict):
        external_id = release.source_ids.get(source)
    if external_id:
        lines.append(f"- id: `{external_id}`")

    tracks = sorted(
        (t for t in release.tracks if _track_has_source(t, source) or not t.source_ids),
        key=lambda t: (t.track_number is None, t.track_number or 0, t.title),
    )
    if not tracks:
        tracks = sorted(
            release.tracks,
            key=lambda t: (t.track_number is None, t.track_number or 0, t.title),
        )
    if tracks:
        lines.append(f"- tracks ({len(tracks)}):")
        for track in tracks:
            duration = _fmt_duration(track.duration_ms)
            suffix = f" ({duration})" if duration else ""
            play = f", plays={track.play_count}" if track.play_count is not None else ""
            lines.append(f"  - {track.title}{suffix}{play}")
    else:
        lines.append("- tracks: none synced")
    return "\n".join(lines)


def _generate_music_platform_doc(
    session: Session, source: str, account: PlatformAccount | None
) -> str:
    artist = _resolve_music_artist_for_source(session, source, account)
    releases = _load_music_releases(session, source=source, artist=artist)
    track_count = sum(len(r.tracks) for r in releases)

    lines = [
        (
            f"---\nsource: {source}\nkind: music\n"
            f"generated_at: {datetime.now(timezone.utc).isoformat()}\n"
            f"release_count: {len(releases)}\ntrack_count: {track_count}\n---\n"
        ),
        f"# {source.title()}\n",
        f"Status: {account.status if account else 'disconnected'}\n",
    ]
    if account:
        if account.username or account.display_name:
            lines.append(f"Account: @{account.username or account.display_name}")
        if account.external_id:
            lines.append(f"External id: `{account.external_id}`")
        if account.last_synced_at:
            lines.append(f"Last synced: {_fmt_dt(account.last_synced_at)}")
    if artist:
        genres = ", ".join((artist.genres or [])[:8])
        lines.append(f"Artist: {artist.name}")
        lines.append(f"Genres: {genres or 'unknown'}")
        followers = (artist.follower_counts or {}).get(source)
        if followers is not None:
            lines.append(f"Followers: {followers}")
        related = artist.related_artists or []
        if related:
            names = [
                (r.get("name") if isinstance(r, dict) else str(r))
                for r in related[:8]
            ]
            lines.append(f"Related: {', '.join(n for n in names if n)}")
    elif account and account.meta:
        genres = account.meta.get("genres") if isinstance(account.meta, dict) else None
        if genres:
            lines.append(f"Genres: {', '.join(genres[:8])}")
        followers = account.meta.get("follower_count") if isinstance(account.meta, dict) else None
        if followers is not None:
            lines.append(f"Followers: {followers}")

    lines.append("")
    lines.append("## Catalog summary\n")
    if releases:
        lines.append(f"{len(releases)} releases, {track_count} tracks synced from {source}.")
    else:
        lines.append("No catalog releases synced yet.")
    lines.append("")
    lines.append("## Releases\n")
    if not releases:
        lines.append("_No releases synced._")
    else:
        for release in releases:
            lines.append(_format_release_block(release, source=source))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_platform_doc(session: Session, source: str) -> str:
    account = session.scalar(select(PlatformAccount).where(PlatformAccount.source == source))
    if source in _MUSIC_SOURCES:
        return _generate_music_platform_doc(session, source, account)

    posts = _load_posts(session, source=source)
    lines = [
        f"---\nsource: {source}\ngenerated_at: {datetime.now(timezone.utc).isoformat()}\npost_count: {len(posts)}\n---\n",
        f"# {source.title()}\n",
        f"Status: {account.status if account else 'disconnected'}\n",
    ]
    if account:
        if account.username or account.display_name:
            lines.append(f"Account: @{account.username or account.display_name}")
        if account.external_id:
            lines.append(f"External id: `{account.external_id}`")
        if account.last_synced_at:
            lines.append(f"Last synced: {_fmt_dt(account.last_synced_at)}")
    if account and account.meta:
        caveats = (account.meta or {}).get("caveats")
        if caveats:
            lines.append(f"Caveats: `{caveats}`")
        analytics = (account.meta or {}).get("analytics_daily")
        if analytics:
            lines.append(f"Analytics daily (raw summary available): {len(analytics)} rows")
    lines.append("")
    lines.append("## Engagement summary\n")
    lines.append(_engagement_summary(posts))
    lines.append("")
    lines.append("## All posts\n")
    if not posts:
        lines.append("_No posts synced._")
    else:
        for p in posts:
            lines.append(
                _format_post_block(
                    p,
                    include_source=False,
                    include_comments=True,
                    caption_limit=None,
                )
            )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def regenerate_all_context(session: Session) -> None:
    profile = generate_artist_profile(session)
    existing = repo.get_context_document(session, "artist_profile")
    locks = (existing.section_locks if existing else None) or {}
    # Preserve locked section bodies by merging markers — MVP: skip overwrite if fully locked
    if locks and all(locks.values()):
        pass
    else:
        repo.upsert_context_document(
            session,
            slug="artist_profile",
            title="Artist Profile",
            body_markdown=profile,
            front_matter={"generated_at": datetime.now(timezone.utc).isoformat()},
            section_locks=locks,
        )

    accounts = {a.source: a for a in session.scalars(select(PlatformAccount))}
    for source in _PLATFORM_SOURCES:
        slug = f"platform_{source}"
        account = accounts.get(source)
        if not _is_configured(account):
            stale = repo.get_context_document(session, slug)
            if stale is not None:
                session.delete(stale)
            continue
        body = generate_platform_doc(session, source)
        repo.upsert_context_document(
            session,
            slug=slug,
            title=f"Platform: {source}",
            body_markdown=body,
        )
    # Drop legacy events context doc if present from older schemas
    legacy = repo.get_context_document(session, "events")
    if legacy is not None:
        session.delete(legacy)
    session.flush()
