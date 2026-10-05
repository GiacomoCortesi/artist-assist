"""Sync orchestration: fetch → upsert → tag → music merge → context hook."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters import list_registered_sources
from app.adapters.base import (
    AccountProfile,
    AdapterError,
    ArtistProfile,
    CredentialError,
    PlatformAdapter,
    PostItem,
    ReleaseItem,
)
from app.adapters.deezer import DeezerAdapter
from app.adapters.facebook import FacebookAdapter
from app.adapters.instagram import InstagramAdapter
from app.adapters.music_merge import consensus_genres, normalize_title
from app.adapters.soundcloud import SoundCloudAdapter
from app.adapters.spotify import SpotifyAdapter
from app.adapters.threads import ThreadsAdapter
from app.adapters.tiktok import TikTokAdapter
from app.adapters.youtube import YouTubeAdapter
from app.config import get_settings
from app.db import repository as repo
from app.db.models import Comment, PlatformAccount, Post, PostTopicTag, SyncRun

logger = logging.getLogger(__name__)

ContextRegenHook = Callable[[Session], None]

# Newest posts first from APIs; one comment HTTP call per post — raise carefully.
COMMENT_FETCH_LIMIT = 120

_sync_lock = threading.Lock()

DEFAULT_TOPICS = [
    ("release", "Release"),
    ("gig", "Gig / show"),
    ("studio", "Studio / writing"),
    ("tour", "Tour"),
    ("merch", "Merch"),
    ("collab", "Collaboration"),
    ("behind_the_scenes", "Behind the scenes"),
    ("fan_love", "Fan love"),
    ("announcement", "Announcement"),
    ("throwback", "Throwback"),
    ("visuals", "Visuals / video"),
    ("playlist", "Playlist"),
]


def _keyword_topics(text: str) -> list[str]:
    t = (text or "").casefold()
    hits: list[str] = []
    rules = {
        "gig": ["gig", "show", "doors", "tour", "live at", "concert"],
        "release": ["out now", "single", "album", "ep ", "streaming", "release"],
        "studio": ["studio", "writing", "session", "recording"],
        "merch": ["merch", "shirt", "vinyl"],
        "visuals": ["video", "visual", "teaser", "reel"],
        "collab": ["feat", "collab", "with @"],
    }
    for slug, words in rules.items():
        if any(w in t for w in words):
            hits.append(slug)
    return hits or ["announcement"]


def _keyword_sentiment(text: str) -> tuple[str, str]:
    t = (text or "").casefold()
    if any(w in t for w in ("love", "amazing", "stunning", "best", "can't wait", "see you")):
        return "positive", "praise"
    if any(w in t for w in ("hate", "terrible", "worst", "refund")):
        return "negative", "complaint"
    if "?" in t:
        return "neutral", "question"
    return "neutral", "general"


class SyncService:
    def __init__(
        self,
        session: Session,
        *,
        context_regen: ContextRegenHook | None = None,
        llm_tagger: Callable[[str, str], Any] | None = None,
    ) -> None:
        self.session = session
        self.context_regen = context_regen
        self.llm_tagger = llm_tagger  # unused in fixture mode; keyword fallback

    def build_adapter(self, source: str) -> PlatformAdapter | None:
        account = self.session.scalar(
            select(PlatformAccount).where(PlatformAccount.source == source)
        )
        token = repo.load_account_token(self.session, account) if account else None
        # Fixture mode adapters work without tokens
        factories: dict[str, Callable[[], PlatformAdapter]] = {
            "spotify": lambda: SpotifyAdapter(
                access_token=token, artist_id=account.external_id if account else None
            ),
            "soundcloud": lambda: SoundCloudAdapter(
                access_token=token, user_id=account.external_id if account else None
            ),
            "deezer": lambda: DeezerAdapter(
                access_token=token, artist_id=account.external_id if account else None
            ),
            "instagram": lambda: InstagramAdapter(
                access_token=token, ig_user_id=account.external_id if account else None
            ),
            "facebook": lambda: FacebookAdapter(
                access_token=token, page_id=account.external_id if account else None
            ),
            "threads": lambda: ThreadsAdapter(
                access_token=token, user_id=account.external_id if account else None
            ),
            "tiktok": lambda: TikTokAdapter(access_token=token),
            "youtube": lambda: YouTubeAdapter(
                access_token=token, channel_id=account.external_id if account else None
            ),
        }
        factory = factories.get(source)
        return factory() if factory else None

    def ensure_taxonomy(self) -> None:
        for slug, label in DEFAULT_TOPICS:
            repo.ensure_topic(self.session, slug, label)

    def _commit(self) -> None:
        """Release SQLite write locks between network I/O."""
        self.session.commit()

    def sync_source(self, source: str) -> dict[str, Any]:
        settings = get_settings()
        mode = "fixture" if settings.use_fixtures else "live"
        account = self.session.scalar(
            select(PlatformAccount).where(PlatformAccount.source == source)
        )
        token = repo.load_account_token(self.session, account) if account else None
        logger.info(
            "Sync start %s mode=%s token=%s external_id=%s",
            source,
            mode,
            bool(token),
            account.external_id if account else None,
        )
        adapter = self.build_adapter(source)
        if adapter is None:
            logger.warning("Sync skipped %s: unknown source", source)
            return {
                "source": source,
                "status": "skipped",
                "mode": mode,
                "error": "unknown source",
            }
        try:
            # Do not hold a write lock across HTTP profile/post fetches.
            self._commit()
            profile = adapter.fetch_profile()
            account = self._persist_profile(profile)
            self._commit()
            posts_count = 0
            comments_count = 0
            releases_count = 0
            comments_left = COMMENT_FETCH_LIMIT

            if adapter.capabilities.can_read_posts:
                seen_external_ids: set[str] = set()
                for page in adapter.iter_posts():
                    page_refs: list[tuple[int, str]] = []
                    for item in page.items:
                        assert isinstance(item, PostItem)
                        post = repo.upsert_post(
                            self.session,
                            source=item.source,
                            external_id=item.external_id,
                            permalink=item.permalink,
                            caption=item.caption,
                            posted_at=item.posted_at,
                            media_type=item.media_type,
                            like_count=item.like_count,
                            comment_count=item.comment_count,
                            view_count=item.view_count,
                            raw=item.raw,
                        )
                        page_refs.append((post.id, item.external_id))
                        seen_external_ids.add(item.external_id)
                        posts_count += 1
                    self._commit()
                    if adapter.capabilities.can_read_comments:
                        for post_id, external_id in page_refs:
                            if comments_left <= 0:
                                break
                            comments_left -= 1
                            post = self.session.get(Post, post_id)
                            if post is None:
                                continue
                            for cpage in adapter.iter_comments(external_id):
                                for c in cpage.items:
                                    repo.add_comment(
                                        self.session,
                                        post,
                                        source=c.source,
                                        external_id=c.external_id,
                                        author_name=c.author_name,
                                        body=c.body,
                                        commented_at=c.commented_at,
                                        raw=c.raw,
                                    )
                                    comments_count += 1
                                self._commit()
                # Live mode: drop posts not seen in this successful full sync.
                if not settings.use_fixtures:
                    repo.delete_posts_except(self.session, source, seen_external_ids)
                    self._commit()

            if adapter.capabilities.can_read_catalog:
                for page in adapter.iter_catalog():
                    for rel in page.items:
                        assert isinstance(rel, ReleaseItem)
                        self._persist_release(rel, account)
                        releases_count += 1
                    self._commit()

            if source == "youtube" and isinstance(adapter, YouTubeAdapter):
                analytics = adapter.fetch_analytics_daily()
                account = self.session.scalar(
                    select(PlatformAccount).where(PlatformAccount.source == source)
                )
                if account is not None:
                    meta = dict(account.meta or {})
                    meta["analytics_daily"] = analytics
                    meta["quota"] = adapter.quota_status()
                    account.meta = meta

            account = self.session.scalar(
                select(PlatformAccount).where(PlatformAccount.source == source)
            )
            if account is None:
                raise AdapterError(f"{source}: account missing after sync")
            account.last_synced_at = datetime.now(timezone.utc)
            account.last_error = None
            account.status = "connected"
            self._commit()
            result = {
                "source": source,
                "status": "ok",
                "mode": mode,
                "external_id": account.external_id,
                "display_name": account.display_name,
                "posts": posts_count,
                "comments": comments_count,
                "releases": releases_count,
            }
            logger.info(
                "Sync ok %s mode=%s external_id=%s posts=%d comments=%d releases=%d",
                source,
                mode,
                account.external_id,
                posts_count,
                comments_count,
                releases_count,
            )
            return result
        except CredentialError as exc:
            logger.warning("Sync skipped %s (live credentials missing): %s", source, exc)
            account = self.session.scalar(
                select(PlatformAccount).where(PlatformAccount.source == source)
            )
            if account is None:
                account = repo.upsert_platform_account(
                    self.session, source=source, status="needs_auth"
                )
            # Live mode: never keep fixture display/id when credentials are missing.
            if not settings.use_fixtures:
                repo.delete_posts_for_source(self.session, source)
                if source in ("spotify", "soundcloud", "deezer"):
                    repo.wipe_music_ids_for_source(self.session, source)
                repo.clear_platform_identity(
                    self.session,
                    account,
                    status="needs_auth",
                    last_error=str(exc),
                )
            else:
                account.status = "needs_auth"
                account.last_error = str(exc)
            self._commit()
            return {
                "source": source,
                "status": "skipped",
                "mode": mode,
                "reason": str(exc),
            }
        except AdapterError as exc:
            logger.exception("Sync failed for %s", source)
            account = repo.upsert_platform_account(
                self.session, source=source, status="error"
            )
            account.last_error = str(exc)
            self._commit()
            return {
                "source": source,
                "status": "error",
                "mode": mode,
                "error": str(exc),
            }

    def _persist_profile(self, profile: AccountProfile | ArtistProfile) -> PlatformAccount:
        from_fixtures = get_settings().use_fixtures
        if isinstance(profile, ArtistProfile):
            # Empty fixture/no-data profiles must not write dummy ids into live DB.
            if not profile.external_id and not profile.name:
                account = repo.upsert_platform_account(
                    self.session,
                    source=profile.source,
                    status="needs_auth",
                    meta={"from_fixtures": from_fixtures, "no_data": True},
                    no_data=True,
                )
                if not from_fixtures:
                    repo.clear_platform_identity(self.session, account, status="needs_auth")
                return account
            account = repo.upsert_platform_account(
                self.session,
                source=profile.source,
                external_id=profile.external_id,
                display_name=profile.name,
                avatar_url=profile.image_url,
                status="connected",
                meta={
                    "follower_count": profile.follower_count,
                    "genres": profile.genres,
                    "from_fixtures": from_fixtures,
                },
                no_data=bool((profile.meta or {}).get("no_data")),
            )
            artist = repo.resolve_music_artist(
                self.session,
                name=profile.name or "Artist",
                source=profile.source,
                external_id=profile.external_id,
            )
            artist.genres = consensus_genres(
                [list(artist.genres or []), list(profile.genres or [])]
            )
            if profile.image_url:
                artist.image_url = profile.image_url
            counts = dict(artist.follower_counts or {})
            if profile.follower_count is not None:
                counts[profile.source] = profile.follower_count
            artist.follower_counts = counts
            if profile.related_artists:
                artist.related_artists = profile.related_artists
            return account
        return repo.upsert_platform_account(
            self.session,
            source=profile.source,
            external_id=profile.external_id,
            display_name=profile.display_name,
            username=profile.username,
            profile_url=profile.profile_url,
            avatar_url=profile.avatar_url,
            status="connected",
            meta={
                **(profile.meta or {}),
                "follower_count": profile.follower_count,
                "from_fixtures": from_fixtures,
            },
        )

    def _persist_release(self, rel: ReleaseItem, account: PlatformAccount) -> None:
        artist = None
        if account.display_name:
            artist = repo.resolve_music_artist(
                self.session,
                name=account.display_name,
                source=account.source if account.source in ("spotify", "soundcloud", "deezer") else None,
                external_id=account.external_id,
            )
        release = repo.upsert_music_release(
            self.session,
            title=rel.title,
            normalized_title=normalize_title(rel.title),
            release_date=rel.release_date,
            artist_id=artist.id if artist else None,
            album_type=rel.album_type,
            cover_url=rel.cover_url,
            genres=rel.genres,
            source=rel.source,
            source_id=rel.external_id,
        )
        for track in rel.tracks:
            repo.upsert_music_track(
                self.session,
                title=track.title,
                normalized_title=normalize_title(track.title),
                release_id=release.id,
                artist_id=artist.id if artist else None,
                duration_ms=track.duration_ms,
                source=track.source,
                source_id=track.external_id,
            )

    def tag_untagged(self) -> dict[str, int]:
        self.ensure_taxonomy()
        tagged_posts = 0
        tagged_comments = 0
        posts = list(self.session.scalars(select(Post)))
        for post in posts:
            existing = list(
                self.session.scalars(select(PostTopicTag).where(PostTopicTag.post_id == post.id))
            )
            if existing:
                continue
            for slug in _keyword_topics(post.caption or ""):
                topic = repo.ensure_topic(self.session, slug, slug.replace("_", " ").title())
                self.session.add(PostTopicTag(post_id=post.id, topic_id=topic.id, confidence=0.7))
                tagged_posts += 1
        comments = list(self.session.scalars(select(Comment).where(Comment.sentiment.is_(None))))
        for comment in comments:
            sentiment, theme = _keyword_sentiment(comment.body or "")
            comment.sentiment = sentiment
            comment.theme = theme
            tagged_comments += 1
        self.session.flush()
        return {"posts": tagged_posts, "comments": tagged_comments}

    def run(
        self,
        *,
        sources: list[str] | None = None,
        trigger: str = "manual",
        run_id: int | None = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        mode = "fixture" if settings.use_fixtures else "live"
        if run_id is not None:
            run = self.session.get(SyncRun, run_id)
            if run is None:
                raise AdapterError(f"sync run #{run_id} not found")
        else:
            run = repo.create_sync_run(self.session, trigger=trigger)
            self._commit()
        targets = sources or [
            s
            for s in (
                "spotify",
                "soundcloud",
                "deezer",
                "instagram",
                "facebook",
                "threads",
                "tiktok",
                "youtube",
            )
            if s in list_registered_sources() or True
        ]
        logger.info("Sync run #%s trigger=%s mode=%s sources=%s", run.id, trigger, mode, targets)
        per_source: dict[str, Any] = {}
        for source in targets:
            per_source[source] = self.sync_source(source)
            run = self.session.get(SyncRun, run.id)
            if run is not None:
                run.per_source = dict(per_source)
                self._commit()
        tags = self.tag_untagged()
        self._commit()
        if self.context_regen:
            try:
                self.context_regen(self.session)
                self._commit()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Context regen failed")
                per_source["_context"] = {"status": "error", "error": str(exc)}
                self._commit()

        statuses = [v.get("status") for k, v in per_source.items() if not k.startswith("_")]
        if all(s == "ok" for s in statuses):
            overall = "success"
        elif any(s == "ok" for s in statuses):
            overall = "partial"
        elif any(s == "skipped" for s in statuses):
            overall = "partial"
        else:
            overall = "failed"
        run = self.session.get(SyncRun, run.id)
        assert run is not None
        repo.finish_sync_run(self.session, run, status=overall, per_source=per_source)
        self._commit()
        logger.info("Sync run #%s finished status=%s per_source=%s", run.id, overall, per_source)
        return {
            "run_id": run.id,
            "status": overall,
            "per_source": per_source,
            "tagged": tags,
            "toast": {
                "type": "success" if overall == "success" else "warning" if overall == "partial" else "error",
                "message": f"Sync {overall}",
            },
        }


def begin_manual_sync(
    session: Session,
    *,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """Create a sync run and start it in a background thread (or report busy)."""
    if not _sync_lock.acquire(blocking=False):
        latest = session.scalar(select(SyncRun).order_by(SyncRun.id.desc()).limit(1))
        return {
            "run_id": latest.id if latest else None,
            "status": "running",
            "per_source": (latest.per_source if latest else {}) or {},
            "toast": {"type": "warning", "message": "Sync already in progress"},
        }

    try:
        run = repo.create_sync_run(session, trigger="manual")
        session.commit()
        run_id = run.id
    except Exception:
        _sync_lock.release()
        raise

    def _job() -> None:
        from app.context.generator import regenerate_all_context
        from app.db import get_session_factory

        job_session = get_session_factory()()
        try:
            SyncService(job_session, context_regen=regenerate_all_context).run(
                sources=sources, trigger="manual", run_id=run_id
            )
        except Exception:  # noqa: BLE001
            logger.exception("Background sync run #%s failed", run_id)
            try:
                failed = job_session.get(SyncRun, run_id)
                if failed is not None and failed.status == "running":
                    repo.finish_sync_run(
                        job_session,
                        failed,
                        status="failed",
                        error_summary="Background sync crashed",
                    )
                    job_session.commit()
            except Exception:  # noqa: BLE001
                logger.exception("Failed to mark sync run #%s as failed", run_id)
                job_session.rollback()
        finally:
            job_session.close()
            _sync_lock.release()

    threading.Thread(target=_job, name=f"sync-{run_id}", daemon=True).start()
    return {
        "run_id": run_id,
        "status": "running",
        "per_source": {},
        "toast": {"type": "success", "message": "Sync started"},
    }


def run_with_lock(
    *,
    sources: list[str] | None = None,
    trigger: str = "scheduled",
) -> dict[str, Any] | None:
    """Run sync synchronously if lock is free (scheduler). Returns None if busy."""
    if not _sync_lock.acquire(blocking=False):
        logger.warning("Skipping %s sync; another sync is already running", trigger)
        return None
    from app.context.generator import regenerate_all_context
    from app.db import get_session_factory

    session = get_session_factory()()
    try:
        return SyncService(session, context_regen=regenerate_all_context).run(
            sources=sources, trigger=trigger
        )
    finally:
        session.close()
        _sync_lock.release()
