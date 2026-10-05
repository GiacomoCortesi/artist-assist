#!/usr/bin/env python3
"""Obtain Meta tokens via local OAuth loopback and write .env bootstrap keys."""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

# Ensure backend package is importable when run as a script from repo root.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings  # noqa: E402
from app.security.meta_oauth import (  # noqa: E402
    FACEBOOK_SCOPES,
    THREADS_SCOPES,
    build_facebook_auth_url,
    build_threads_auth_url,
    exchange_facebook_code,
    exchange_facebook_long_lived,
    exchange_threads_code,
    exchange_threads_long_lived,
    fetch_pages,
    fetch_threads_profile,
    fetch_token_debug,
    obtain_oauth_code,
    parse_meta_services,
    pick_page,
    upsert_env_file,
    validate_facebook_tokens,
    validate_threads_token,
)


def _repo_root() -> Path:
    return BACKEND_ROOT.parent


def _env_path() -> Path:
    return _repo_root() / ".env"


def _require_meta_app(settings) -> tuple[str, str]:
    if not settings.meta_app_id or not settings.meta_app_secret:
        raise SystemExit("META_APP_ID and META_APP_SECRET must be set in .env")
    return settings.meta_app_id, settings.meta_app_secret


def run_check(settings) -> int:
    import httpx

    ok = True
    with httpx.Client(timeout=30.0) as client:
        if settings.meta_page_access_token and settings.meta_page_id and settings.meta_ig_user_id:
            try:
                validate_facebook_tokens(
                    page_access_token=settings.meta_page_access_token,
                    page_id=settings.meta_page_id,
                    ig_user_id=settings.meta_ig_user_id,
                    client=client,
                )
                print("Facebook Page + Instagram: OK")
            except Exception as exc:  # noqa: BLE001
                ok = False
                print(f"Facebook Page + Instagram: FAIL ({exc})")
        else:
            ok = False
            print("Facebook Page + Instagram: missing META_PAGE_* / META_IG_USER_ID")

        if settings.threads_access_token and settings.threads_user_id:
            try:
                validate_threads_token(
                    access_token=settings.threads_access_token,
                    user_id=settings.threads_user_id,
                    client=client,
                )
                print("Threads: OK")
            except Exception as exc:  # noqa: BLE001
                ok = False
                print(f"Threads: FAIL ({exc})")
        else:
            print("Threads: not configured (optional)")

    return 0 if ok else 1


def run_facebook_leg(
    *,
    app_id: str,
    app_secret: str,
    port: int,
    page_id: str | None,
    token: str | None,
    require_instagram: bool,
) -> dict[str, str]:
    if token:
        short_lived = token.strip()
        print("Using provided Facebook short-lived token.")
    else:
        state = secrets.token_urlsafe(24)
        auth_url = build_facebook_auth_url(app_id=app_id, port=port, state=state)
        print("\nFacebook / Instagram scopes:", ", ".join(FACEBOOK_SCOPES))
        code = obtain_oauth_code(auth_url=auth_url, port=port, state=state)
        short_lived = exchange_facebook_code(
            app_id=app_id, app_secret=app_secret, code=code, port=port
        )

    long_lived = exchange_facebook_long_lived(
        app_id=app_id, app_secret=app_secret, short_lived_token=short_lived
    )
    pages = fetch_pages(user_token=long_lived)
    if not pages:
        try:
            debug = fetch_token_debug(user_token=long_lived)
            print("\nOAuth OK, but /me/accounts returned no Pages.")
            print(f"  Logged in as: {debug['user_name']} ({debug['user_id']})")
            print(f"  Granted: {', '.join(debug['granted']) or '(none)'}")
            if debug["declined"]:
                print(f"  Declined: {', '.join(debug['declined'])}")
            print(
                "  Fix: re-run and grant business_management + Page access; "
                "Pages under Meta Business Suite need business_management or "
                "/me/accounts stays empty. In Dev mode, add this FB user as "
                "App Admin/Developer/Tester."
            )
        except Exception as exc:  # noqa: BLE001
            print(f"\nCould not fetch token debug info: {exc}")
    page = pick_page(pages, page_id)
    updates = {
        "META_PAGE_ACCESS_TOKEN": page.access_token,
        "META_PAGE_ID": page.page_id,
    }
    if page.ig_user_id:
        updates["META_IG_USER_ID"] = page.ig_user_id
    elif require_instagram:
        raise SystemExit(
            f"Page {page.name!r} has no linked Instagram Business account. "
            "Link IG to the Page in Meta Business settings, then retry."
        )
    else:
        print(
            f"Page {page.name!r} has no linked Instagram account "
            "(ok: Instagram not selected)."
        )
    return updates


def run_threads_leg(
    *,
    app_id: str,
    app_secret: str,
    port: int,
    threads_token: str | None,
) -> dict[str, str]:
    if threads_token:
        short_lived = threads_token.strip()
        print("Using provided Threads short-lived token.")
    else:
        state = secrets.token_urlsafe(24)
        auth_url = build_threads_auth_url(app_id=app_id, port=port, state=state)
        print("\nThreads scopes:", ", ".join(THREADS_SCOPES))
        code = obtain_oauth_code(auth_url=auth_url, port=port, state=state)
        short_lived = exchange_threads_code(
            app_id=app_id, app_secret=app_secret, code=code, port=port
        )

    long_lived = exchange_threads_long_lived(app_secret=app_secret, short_lived_token=short_lived)
    profile = fetch_threads_profile(access_token=long_lived)
    return {
        "THREADS_ACCESS_TOKEN": long_lived,
        "THREADS_USER_ID": profile["id"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Obtain Meta tokens for ArtistAssist live sync")
    parser.add_argument("--write-env", action="store_true", help="Upsert token keys into repo .env")
    parser.add_argument("--check", action="store_true", help="Validate current .env Meta tokens")
    parser.add_argument("--port", type=int, default=8765, help="Local OAuth callback port (default 8765)")
    parser.add_argument("--page-id", help="Facebook Page id (skip interactive pick)")
    parser.add_argument("--token", help="Facebook short-lived user token (skip browser OAuth)")
    parser.add_argument("--threads-token", help="Threads short-lived token (skip browser OAuth)")
    parser.add_argument(
        "--services",
        default="all",
        help="Comma-separated: all | facebook|fb,instagram|ig,threads (default: all)",
    )
    parser.add_argument(
        "--skip-threads",
        action="store_true",
        help="Deprecated: same as --services without threads",
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.check:
        return run_check(settings)

    try:
        services = set(parse_meta_services(args.services))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.skip_threads:
        services.discard("threads")
        print("Note: --skip-threads is deprecated; prefer --services facebook,instagram")

    if not services:
        raise SystemExit("No services selected after applying --skip-threads")

    app_id, app_secret = _require_meta_app(settings)
    updates: dict[str, str] = {}

    print("ArtistAssist Meta connect")
    print(f"App id: {app_id}")
    print(f"Services: {', '.join(sorted(services))}")
    print(f"Redirect URI: https://localhost:{args.port}/callback")
    print("Meta App Domains must include: localhost")
    print("Valid OAuth Redirect URIs must include the HTTPS URI above.")
    print("(Local callback uses a self-signed cert — accept the browser warning once.)\n")

    # Instagram Graph API uses the Facebook Page OAuth leg (shared login).
    need_facebook_login = "facebook" in services or "instagram" in services
    if need_facebook_login:
        fb_updates = run_facebook_leg(
            app_id=app_id,
            app_secret=app_secret,
            port=args.port,
            page_id=args.page_id,
            token=args.token,
            require_instagram="instagram" in services,
        )
        # Page token is always written when FB or IG is selected (IG needs the Page token).
        updates.update(fb_updates)
        if updates.get("META_IG_USER_ID"):
            print(f"Selected Page {updates['META_PAGE_ID']} with IG user {updates['META_IG_USER_ID']}")
        else:
            print(f"Selected Page {updates['META_PAGE_ID']}")

    if "threads" in services:
        try:
            updates.update(
                run_threads_leg(
                    app_id=app_id,
                    app_secret=app_secret,
                    port=args.port,
                    threads_token=args.threads_token,
                )
            )
            print(f"Threads user {updates['THREADS_USER_ID']}")
        except Exception as exc:  # noqa: BLE001
            print(f"Threads leg skipped due to error: {exc}")

    if not updates:
        raise SystemExit("No tokens obtained for the selected services")

    if args.write_env:
        upsert_env_file(str(_env_path()), updates)
        print(f"\nWrote {len(updates)} keys to {_env_path()}")
        print("Set PLATFORM_LIVE=1 and restart the backend to sync live Meta data.")
    else:
        print("\nAdd to .env (or rerun with --write-env):\n")
        for key, value in updates.items():
            print(f"{key}={value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
