"""Adapter interface tests."""

from __future__ import annotations

import pytest

from app.adapters import list_registered_sources
from app.adapters.base import Capabilities, RateLimitError, with_retries
from app.adapters.fake import FakeAdapter


def test_capabilities_never_publish() -> None:
    caps = Capabilities(can_read_posts=True, can_publish=True, can_schedule=True)
    assert caps.can_publish is False
    assert caps.can_schedule is False


def test_fake_adapter_typed_pages() -> None:
    adapter = FakeAdapter()
    profile = adapter.fetch_profile()
    assert profile.external_id == "fake-1"
    pages = list(adapter.iter_posts())
    assert len(pages) == 1
    assert pages[0].items[0].caption == "Hello from fake"
    catalog = list(adapter.iter_catalog())
    assert catalog[0].items[0].title == "Demo EP"
    assert "fake" in list_registered_sources()


def test_retry_then_succeed() -> None:
    adapter = FakeAdapter(fail_rate_limit_times=2)
    adapter.retry_policy.base_delay_seconds = 0.01
    profile = adapter.fetch_profile()
    assert profile.username == "fakeartist"


def test_retry_exhausted() -> None:
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise RateLimitError("nope", retry_after=0.01)

    with pytest.raises(RateLimitError):
        with_retries(boom, policy=FakeAdapter().retry_policy)
    assert calls["n"] == 3
