"""In-memory fake adapter for tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

from app.adapters.base import (
    AccountProfile,
    Capabilities,
    Page,
    PlatformAdapter,
    PostItem,
    RateLimitError,
    ReleaseItem,
    TrackItem,
    register_adapter,
    with_retries,
)


class FakeAdapter(PlatformAdapter):
    source = "fake"

    def __init__(
        self,
        *,
        access_token: str | None = "fake-token",
        fail_rate_limit_times: int = 0,
        posts: list[PostItem] | None = None,
        releases: list[ReleaseItem] | None = None,
    ) -> None:
        super().__init__(access_token=access_token)
        self._rate_limit_remaining = fail_rate_limit_times
        self._posts = posts or [
            PostItem(
                source=self.source,
                external_id="p1",
                caption="Hello from fake",
                posted_at=datetime.now(timezone.utc),
            )
        ]
        self._releases = releases or [
            ReleaseItem(
                source=self.source,
                external_id="r1",
                title="Demo EP",
                release_date="2024-01-01",
                tracks=[
                    TrackItem(source=self.source, external_id="t1", title="Track One", duration_ms=180000)
                ],
            )
        ]

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(can_read_posts=True, can_read_catalog=True, can_read_comments=True)

    def fetch_profile(self) -> AccountProfile:
        def _call() -> AccountProfile:
            if self._rate_limit_remaining > 0:
                self._rate_limit_remaining -= 1
                raise RateLimitError("slow down", retry_after=0.01)
            return AccountProfile(
                source=self.source,
                external_id="fake-1",
                display_name="Fake Artist",
                username="fakeartist",
            )

        return with_retries(_call, policy=self.retry_policy, secrets=[self.access_token or ""])

    def iter_posts(self, *, cursor: str | None = None) -> Iterator[Page]:
        yield Page(items=self._posts, cursor=None, has_more=False)

    def iter_catalog(self, *, cursor: str | None = None) -> Iterator[Page]:
        yield Page(items=self._releases, cursor=None, has_more=False)


register_adapter("fake", FakeAdapter)
