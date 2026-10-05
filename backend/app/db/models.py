"""SQLAlchemy ORM models for ArtistAssist."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PlatformAccount(Base, TimestampMixin):
    __tablename__ = "platform_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    external_id: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255))
    profile_url: Mapped[str | None] = mapped_column(String(512))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="disconnected", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    no_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    token: Mapped[EncryptedToken | None] = relationship(
        back_populates="account", uselist=False, cascade="all, delete-orphan"
    )


class EncryptedToken(Base, TimestampMixin):
    __tablename__ = "encrypted_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("platform_accounts.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    token_type: Mapped[str] = mapped_column(String(64), default="oauth", nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[str | None] = mapped_column(Text)

    account: Mapped[PlatformAccount] = relationship(back_populates="token")


class Post(Base, TimestampMixin):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_post_source_ext"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    permalink: Mapped[str | None] = mapped_column(String(1024))
    caption: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    media_type: Mapped[str | None] = mapped_column(String(64))
    like_count: Mapped[int | None] = mapped_column(Integer)
    comment_count: Mapped[int | None] = mapped_column(Integer)
    view_count: Mapped[int | None] = mapped_column(Integer)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    comments: Mapped[list[Comment]] = relationship(back_populates="post", cascade="all, delete-orphan")
    topic_tags: Mapped[list[PostTopicTag]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )
    media_assets: Mapped[list[MediaAsset]] = relationship(back_populates="source_post")


class Comment(Base, TimestampMixin):
    __tablename__ = "comments"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_comment_source_ext"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    commented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sentiment: Mapped[str | None] = mapped_column(String(32))
    theme: Mapped[str | None] = mapped_column(String(128))
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    post: Mapped[Post] = relationship(back_populates="comments")


class MediaAsset(Base, TimestampMixin):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # original | variant
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("media_assets.id", ondelete="SET NULL"))
    source_post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id", ondelete="SET NULL"))
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(128))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    format_preset: Mapped[str | None] = mapped_column(String(64))
    crop_box: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # {x,y,w,h}
    focal_point: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # {x,y} 0-1
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    source_post: Mapped[Post | None] = relationship(back_populates="media_assets")
    parent: Mapped[MediaAsset | None] = relationship(remote_side="MediaAsset.id")


class MusicArtist(Base, TimestampMixin):
    __tablename__ = "music_artists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    spotify_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    soundcloud_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    deezer_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    genres: Mapped[list[Any] | None] = mapped_column(JSON, default=list)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    follower_counts: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    related_artists: Mapped[list[Any] | None] = mapped_column(JSON, default=list)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class MusicRelease(Base, TimestampMixin):
    __tablename__ = "music_releases"
    __table_args__ = (UniqueConstraint("normalized_title", "release_date", name="uq_release_norm"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artist_id: Mapped[int | None] = mapped_column(ForeignKey("music_artists.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    release_date: Mapped[str | None] = mapped_column(String(32))  # YYYY-MM-DD or YYYY
    album_type: Mapped[str | None] = mapped_column(String(64))
    cover_url: Mapped[str | None] = mapped_column(String(1024))
    genres: Mapped[list[Any] | None] = mapped_column(JSON, default=list)
    spotify_id: Mapped[str | None] = mapped_column(String(64))
    soundcloud_id: Mapped[str | None] = mapped_column(String(64))
    deezer_id: Mapped[str | None] = mapped_column(String(64))
    source_ids: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    tracks: Mapped[list[MusicTrack]] = relationship(
        back_populates="release", cascade="all, delete-orphan"
    )


class MusicTrack(Base, TimestampMixin):
    __tablename__ = "music_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    release_id: Mapped[int | None] = mapped_column(ForeignKey("music_releases.id", ondelete="SET NULL"))
    artist_id: Mapped[int | None] = mapped_column(ForeignKey("music_artists.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    track_number: Mapped[int | None] = mapped_column(Integer)
    isrc: Mapped[str | None] = mapped_column(String(32))
    spotify_id: Mapped[str | None] = mapped_column(String(64))
    soundcloud_id: Mapped[str | None] = mapped_column(String(64))
    deezer_id: Mapped[str | None] = mapped_column(String(64))
    source_ids: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    play_count: Mapped[int | None] = mapped_column(Integer)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    release: Mapped[MusicRelease | None] = relationship(back_populates="tracks")


class TopicTag(Base, TimestampMixin):
    __tablename__ = "topic_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    post_links: Mapped[list[PostTopicTag]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )


class PostTopicTag(Base):
    __tablename__ = "post_topic_tags"
    __table_args__ = (UniqueConstraint("post_id", "topic_id", name="uq_post_topic"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topic_tags.id", ondelete="CASCADE"), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)

    post: Mapped[Post] = relationship(back_populates="topic_tags")
    topic: Mapped[TopicTag] = relationship(back_populates="post_links")


class ContextDocument(Base, TimestampMixin):
    __tablename__ = "context_documents"
    __table_args__ = (UniqueConstraint("slug", name="uq_context_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, default="", nullable=False)
    front_matter: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    section_locks: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)


class ContentPlan(Base, TimestampMixin):
    __tablename__ = "content_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    drafts: Mapped[list[ContentDraft]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class ContentDraft(Base, TimestampMixin):
    __tablename__ = "content_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("content_plans.id", ondelete="SET NULL"))
    thread_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_threads.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(255))
    platform_targets: Mapped[list[Any] | None] = mapped_column(JSON, default=list)
    caption: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[Any] | None] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    media_asset_ids: Mapped[list[Any] | None] = mapped_column(JSON, default=list)
    prepared_assets: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    agent_notes: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    plan: Mapped[ContentPlan | None] = relationship(back_populates="drafts")
    thread: Mapped[AgentThread | None] = relationship(back_populates="drafts")


class AgentThread(Base, TimestampMixin):
    __tablename__ = "agent_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)

    messages: Mapped[list[AgentMessage]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="AgentMessage.id",
    )
    drafts: Mapped[list[ContentDraft]] = relationship(back_populates="thread")


class AgentMessage(Base, TimestampMixin):
    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("agent_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # user | assistant | tool
    content: Mapped[str | None] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(String(64))
    tool_call_id: Mapped[str | None] = mapped_column(String(128))
    tool_calls: Mapped[list[Any] | None] = mapped_column(JSON)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    thread: Mapped[AgentThread] = relationship(back_populates="messages")


class SyncRun(Base, TimestampMixin):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    per_source: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=dict)
    error_summary: Mapped[str | None] = mapped_column(Text)


class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
