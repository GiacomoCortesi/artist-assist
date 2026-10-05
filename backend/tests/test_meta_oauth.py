"""Meta OAuth helper tests (mocked HTTP)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from app.security.meta_oauth import (
    ALL_META_SERVICES,
    exchange_facebook_code,
    exchange_facebook_long_lived,
    exchange_threads_code,
    exchange_threads_long_lived,
    fetch_pages,
    fetch_threads_profile,
    fetch_token_debug,
    make_loopback_ssl_context,
    parse_meta_services,
    pick_page,
    redirect_uri,
    upsert_env_file,
    validate_facebook_tokens,
)


def test_redirect_uri_is_https() -> None:
    assert redirect_uri(8765) == "https://localhost:8765/callback"


def test_parse_meta_services() -> None:
    assert parse_meta_services("all") == ALL_META_SERVICES
    assert parse_meta_services("fb,ig") == frozenset({"facebook", "instagram"})
    assert parse_meta_services("threads") == frozenset({"threads"})
    assert parse_meta_services("facebook,instagram,threads") == ALL_META_SERVICES
    with pytest.raises(ValueError, match="Unknown service"):
        parse_meta_services("tiktok")
    with pytest.raises(ValueError, match="empty"):
        parse_meta_services(" , ")


def test_make_loopback_ssl_context() -> None:
    context, cert_path, key_path = make_loopback_ssl_context()
    assert cert_path.exists()
    assert key_path.exists()
    assert context is not None
    cert_path.unlink(missing_ok=True)
    key_path.unlink(missing_ok=True)
    cert_path.parent.rmdir()


@respx.mock
def test_exchange_facebook_code_and_long_lived() -> None:
    respx.get("https://graph.facebook.com/v21.0/oauth/access_token").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "short-user", "token_type": "bearer"}),
            httpx.Response(200, json={"access_token": "long-user", "token_type": "bearer"}),
        ]
    )
    short = exchange_facebook_code(
        app_id="app1", app_secret="sec", code="abc", port=8765
    )
    assert short == "short-user"
    long = exchange_facebook_long_lived(
        app_id="app1", app_secret="sec", short_lived_token=short
    )
    assert long == "long-user"


@respx.mock
def test_fetch_pages_and_pick() -> None:
    respx.get("https://graph.facebook.com/v21.0/me/accounts").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "111",
                        "name": "Main Page",
                        "access_token": "page-token",
                        "instagram_business_account": {"id": "ig99", "username": "artist"},
                    }
                ]
            },
        )
    )
    pages = fetch_pages(user_token="long-user")
    assert len(pages) == 1
    picked = pick_page(pages, "111")
    assert picked.page_id == "111"
    assert picked.ig_user_id == "ig99"


@respx.mock
def test_fetch_token_debug() -> None:
    respx.get("https://graph.facebook.com/v21.0/me").mock(
        return_value=httpx.Response(200, json={"id": "u1", "name": "Artist"})
    )
    respx.get("https://graph.facebook.com/v21.0/me/permissions").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"permission": "pages_show_list", "status": "granted"},
                    {"permission": "email", "status": "declined"},
                ]
            },
        )
    )
    debug = fetch_token_debug(user_token="long-user")
    assert debug["user_id"] == "u1"
    assert debug["granted"] == ["pages_show_list"]
    assert debug["declined"] == ["email"]


def test_pick_page_empty_explains_oauth_ok() -> None:
    with pytest.raises(ValueError, match="OAuth succeeded"):
        pick_page([], None)


@respx.mock
def test_threads_exchange_and_profile() -> None:
    respx.post("https://graph.threads.net/oauth/access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "threads-short"})
    )
    respx.get("https://graph.threads.net/access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "threads-long"})
    )
    respx.get("https://graph.threads.net/v1.0/me").mock(
        return_value=httpx.Response(200, json={"id": "th1", "username": "artist"})
    )
    short = exchange_threads_code(
        app_id="app1", app_secret="sec", code="xyz", port=8765
    )
    assert short == "threads-short"
    long = exchange_threads_long_lived(app_secret="sec", short_lived_token=short)
    assert long == "threads-long"
    profile = fetch_threads_profile(access_token=long)
    assert profile == {"id": "th1", "username": "artist"}


@respx.mock
def test_validate_facebook_tokens() -> None:
    respx.get("https://graph.facebook.com/v21.0/111").mock(
        return_value=httpx.Response(200, json={"id": "111", "name": "Page"})
    )
    respx.get("https://graph.facebook.com/v21.0/ig99").mock(
        return_value=httpx.Response(200, json={"id": "ig99", "username": "artist"})
    )
    validate_facebook_tokens(
        page_access_token="page-token", page_id="111", ig_user_id="ig99"
    )


def test_upsert_env_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "META_APP_ID=old\nMETA_PAGE_ID=\nOTHER=1\n",
        encoding="utf-8",
    )
    upsert_env_file(
        str(env),
        {"META_PAGE_ID": "111", "META_PAGE_ACCESS_TOKEN": "tok", "NEW_KEY": "x"},
    )
    text = env.read_text(encoding="utf-8")
    assert "META_APP_ID=old" in text
    assert "META_PAGE_ID=111" in text
    assert "META_PAGE_ACCESS_TOKEN=tok" in text
    assert "NEW_KEY=x" in text
    assert "OTHER=1" in text


def test_pick_page_missing_raises() -> None:
    from app.security.meta_oauth import PageAccount

    pages = [
        PageAccount(
            page_id="1",
            name="A",
            access_token="t",
            ig_user_id="ig",
            ig_username="a",
        )
    ]
    with pytest.raises(ValueError, match="not found"):
        pick_page(pages, "missing")
