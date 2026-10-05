"""Read-only platform adapter interface and shared models."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.security.tokens import redact_secrets

logger = logging.getLogger(__name__)


class AdapterError(Exception):
    """Base adapter failure — never treated as success."""


class AuthError(AdapterError):
    pass


class RateLimitError(AdapterError):
    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class NotFoundError(AdapterError):
    pass


class CredentialError(AdapterError):
    """Live sync cannot run — missing OAuth token or confirmed platform identity."""


class Capabilities(BaseModel):
    """Read capabilities only. Publish flags are always false for MVP."""

    model_config = ConfigDict(frozen=True)

    can_read_profile: bool = True
    can_read_posts: bool = False
    can_read_comments: bool = False
    can_read_catalog: bool = False
    can_read_insights: bool = False
    can_publish: bool = False
    can_schedule: bool = False

    def model_post_init(self, __context: Any) -> None:
        # Enforce MVP: never advertise publish/schedule
        object.__setattr__(self, "can_publish", False)
        object.__setattr__(self, "can_schedule", False)


class AccountProfile(BaseModel):
    source: str
    external_id: str
    display_name: str | None = None
    username: str | None = None
    profile_url: str | None = None
    avatar_url: str | None = None
    follower_count: int | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class MediaItem(BaseModel):
    url: str | None = None
    media_type: str | None = None  # image | video | audio | carousel
    width: int | None = None
    height: int | None = None
    thumbnail_url: str | None = None


class PostItem(BaseModel):
    source: str
    external_id: str
    permalink: str | None = None
    caption: str | None = None
    posted_at: datetime | None = None
    media_type: str | None = None
    media: list[MediaItem] = Field(default_factory=list)
    like_count: int | None = None
    comment_count: int | None = None
    view_count: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class CommentItem(BaseModel):
    source: str
    external_id: str
    post_external_id: str
    author_name: str | None = None
    body: str | None = None
    commented_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ArtistProfile(BaseModel):
    source: str
    external_id: str
    name: str
    genres: list[str] = Field(default_factory=list)
    image_url: str | None = None
    follower_count: int | None = None
    related_artists: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class TrackItem(BaseModel):
    source: str
    external_id: str
    title: str
    duration_ms: int | None = None
    track_number: int | None = None
    isrc: str | None = None
    play_count: int | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ReleaseItem(BaseModel):
    source: str
    external_id: str
    title: str
    release_date: str | None = None
    album_type: str | None = None
    cover_url: str | None = None
    genres: list[str] = Field(default_factory=list)
    tracks: list[TrackItem] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[Any]
    cursor: str | None = None
    has_more: bool = False


class RetryPolicy(BaseModel):
    max_attempts: int = 3
    base_delay_seconds: float = 0.25
    max_delay_seconds: float = 4.0

    def delay_for(self, attempt: int) -> float:
        return min(self.base_delay_seconds * (2**attempt), self.max_delay_seconds)


def with_retries(fn, *, policy: RetryPolicy | None = None, secrets: list[str] | None = None):
    """Call fn with exponential backoff on RateLimitError."""
    policy = policy or RetryPolicy()
    last_exc: Exception | None = None
    for attempt in range(policy.max_attempts):
        try:
            return fn()
        except RateLimitError as exc:
            last_exc = exc
            delay = exc.retry_after if exc.retry_after is not None else policy.delay_for(attempt)
            logger.warning(
                "Rate limited (attempt %s/%s), sleeping %.2fs: %s",
                attempt + 1,
                policy.max_attempts,
                delay,
                redact_secrets(str(exc), secrets),
            )
            if attempt + 1 >= policy.max_attempts:
                break
            time.sleep(delay)
        except AdapterError:
            raise
    assert last_exc is not None
    raise last_exc


class PlatformAdapter(ABC):
    """Common read-only adapter contract for music and social platforms."""

    source: str

    def __init__(self, *, access_token: str | None = None) -> None:
        self.access_token = access_token
        self.retry_policy = RetryPolicy()

    @property
    @abstractmethod
    def capabilities(self) -> Capabilities:
        raise NotImplementedError

    def user_agent(self) -> str:
        return get_settings().user_agent

    def _require_live_token(self) -> None:
        use_fixtures = getattr(self, "use_fixtures", get_settings().use_fixtures)
        if not use_fixtures and not self.access_token:
            raise CredentialError(
                f"{self.source}: live sync requires an OAuth token "
                "(connect the platform or bootstrap tokens into .env)"
            )

    def _require_live_artist_id(self) -> None:
        use_fixtures = getattr(self, "use_fixtures", get_settings().use_fixtures)
        artist_id = getattr(self, "artist_id", None)
        if not use_fixtures and not artist_id:
            raise CredentialError(
                f"{self.source}: live sync requires a confirmed artist id "
                "(Settings → Music identity)"
            )

    def authenticate(self) -> None:
        """Optional hook for token exchange / client credentials."""
        return None

    def refresh_auth(self) -> str | None:
        """Refresh access token; return new token or None."""
        return None

    @abstractmethod
    def fetch_profile(self) -> AccountProfile | ArtistProfile:
        raise NotImplementedError

    def iter_posts(self, *, cursor: str | None = None) -> Iterator[Page]:
        yield Page(items=[], cursor=None, has_more=False)

    def iter_comments(self, post_external_id: str, *, cursor: str | None = None) -> Iterator[Page]:
        yield Page(items=[], cursor=None, has_more=False)

    def iter_catalog(self, *, cursor: str | None = None) -> Iterator[Page]:
        yield Page(items=[], cursor=None, has_more=False)

    def search_identity(self, query: str) -> list[AccountProfile | ArtistProfile]:
        return []


# Registry for sync to discover adapters without hard-coding each call site
_ADAPTER_REGISTRY: dict[str, type[PlatformAdapter]] = {}


def register_adapter(source: str, cls: type[PlatformAdapter]) -> None:
    _ADAPTER_REGISTRY[source] = cls


def list_registered_sources() -> list[str]:
    return sorted(_ADAPTER_REGISTRY.keys())
