"""Meta (Facebook/Instagram/Threads) OAuth helpers for the meta-connect CLI."""

from __future__ import annotations

import datetime as dt
import ipaddress
import secrets
import ssl
import tempfile
import threading
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

GRAPH_VERSION = "v21.0"
FACEBOOK_GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
THREADS_GRAPH = "https://graph.threads.net/v1.0"
THREADS_OAUTH = "https://graph.threads.net"

FACEBOOK_SCOPES = [
    "pages_show_list",
    # Required for /me/accounts when the Page is linked to Meta Business Suite
    # (empty data[] otherwise, even with pages_show_list granted).
    "business_management",
    "pages_read_engagement",
    "pages_read_user_content",
    "instagram_basic",
    "instagram_manage_comments",
    "instagram_manage_insights",
]

THREADS_SCOPES = [
    "threads_basic",
    "threads_read_replies",
]

ALL_META_SERVICES = frozenset({"facebook", "instagram", "threads"})
_META_SERVICE_ALIASES = {
    "all": "all",
    "facebook": "facebook",
    "fb": "facebook",
    "instagram": "instagram",
    "ig": "instagram",
    "threads": "threads",
}


def parse_meta_services(raw: str) -> frozenset[str]:
    """Parse comma-separated Meta services (fb/facebook, ig/instagram, threads, all)."""
    parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValueError("services list is empty; use all or fb,instagram,threads")
    selected: set[str] = set()
    for part in parts:
        alias = _META_SERVICE_ALIASES.get(part)
        if alias is None:
            raise ValueError(
                f"Unknown service {part!r}. Use: all, facebook|fb, instagram|ig, threads"
            )
        if alias == "all":
            return ALL_META_SERVICES
        selected.add(alias)
    return frozenset(selected)


@dataclass(frozen=True)
class PageAccount:
    page_id: str
    name: str
    access_token: str
    ig_user_id: str | None
    ig_username: str | None


@dataclass(frozen=True)
class OAuthCallbackResult:
    code: str | None
    error: str | None
    error_description: str | None


def redirect_uri(port: int) -> str:
    # Use localhost (not 127.0.0.1): Meta App Domains accepts hostnames, not raw IPs.
    # HTTPS required by Meta Enforce HTTPS; local cert is self-signed.
    return f"https://localhost:{port}/callback"


def make_loopback_ssl_context() -> tuple[ssl.SSLContext, Path, Path]:
    """Create an ephemeral self-signed cert for the local OAuth HTTPS callback."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ArtistAssist local OAuth"),
        ]
    )
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=1))
        .not_valid_after(now + dt.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    tmp = Path(tempfile.mkdtemp(prefix="artistassist-oauth-"))
    key_path = tmp / "key.pem"
    cert_path = tmp / "cert.pem"
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    return context, cert_path, key_path


def build_facebook_auth_url(*, app_id: str, port: int, state: str) -> str:
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri(port),
        "state": state,
        "scope": ",".join(FACEBOOK_SCOPES),
        "response_type": "code",
        # Re-prompt declined Page/permission choices on retry.
        "auth_type": "rerequest",
    }
    return f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth?{urlencode(params)}"


def build_threads_auth_url(*, app_id: str, port: int, state: str) -> str:
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri(port),
        "scope": ",".join(THREADS_SCOPES),
        "response_type": "code",
        "state": state,
    }
    return f"https://threads.net/oauth/authorize?{urlencode(params)}"


def exchange_facebook_code(
    *,
    app_id: str,
    app_secret: str,
    code: str,
    port: int,
    client: httpx.Client | None = None,
) -> str:
    """Exchange authorization code for a short-lived user access token."""
    params = {
        "client_id": app_id,
        "client_secret": app_secret,
        "redirect_uri": redirect_uri(port),
        "code": code,
    }
    data = _graph_get(f"{FACEBOOK_GRAPH}/oauth/access_token", params=params, client=client)
    token = data.get("access_token")
    if not token:
        raise ValueError(f"Facebook code exchange failed: {data}")
    return str(token)


def exchange_facebook_long_lived(
    *,
    app_id: str,
    app_secret: str,
    short_lived_token: str,
    client: httpx.Client | None = None,
) -> str:
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_lived_token,
    }
    data = _graph_get(f"{FACEBOOK_GRAPH}/oauth/access_token", params=params, client=client)
    token = data.get("access_token")
    if not token:
        raise ValueError(f"Facebook long-lived exchange failed: {data}")
    return str(token)


def fetch_token_debug(*, user_token: str, client: httpx.Client | None = None) -> dict[str, Any]:
    """Return /me + /me/permissions for empty-page troubleshooting (no secrets)."""
    me = _graph_get(
        f"{FACEBOOK_GRAPH}/me",
        params={"fields": "id,name", "access_token": user_token},
        client=client,
    )
    perms = _graph_get(
        f"{FACEBOOK_GRAPH}/me/permissions",
        params={"access_token": user_token},
        client=client,
    )
    granted = [
        str(row.get("permission"))
        for row in (perms.get("data") or [])
        if isinstance(row, dict) and row.get("status") == "granted"
    ]
    declined = [
        str(row.get("permission"))
        for row in (perms.get("data") or [])
        if isinstance(row, dict) and row.get("status") == "declined"
    ]
    return {
        "user_id": str(me.get("id") or ""),
        "user_name": str(me.get("name") or ""),
        "granted": granted,
        "declined": declined,
    }


def fetch_pages(*, user_token: str, client: httpx.Client | None = None) -> list[PageAccount]:
    params = {
        "fields": "id,name,access_token,instagram_business_account{id,username}",
        "access_token": user_token,
    }
    data = _graph_get(f"{FACEBOOK_GRAPH}/me/accounts", params=params, client=client)
    pages: list[PageAccount] = []
    for row in data.get("data") or []:
        ig = row.get("instagram_business_account") or {}
        pages.append(
            PageAccount(
                page_id=str(row["id"]),
                name=str(row.get("name") or row["id"]),
                access_token=str(row["access_token"]),
                ig_user_id=str(ig["id"]) if ig.get("id") else None,
                ig_username=str(ig["username"]) if ig.get("username") else None,
            )
        )
    return pages


def pick_page(pages: list[PageAccount], page_id: str | None) -> PageAccount:
    if not pages:
        raise ValueError(
            "No Facebook Pages returned from /me/accounts. "
            "OAuth succeeded, but this user token has no Page access. "
            "If the Page is in Meta Business Suite, grant business_management "
            "(with pages_show_list). Also check: Page kept selected in Login, "
            "and in Dev mode your FB user is an app role (Admin/Developer/Tester)."
        )
    if page_id:
        for page in pages:
            if page.page_id == page_id:
                return page
        raise ValueError(f"Page id {page_id!r} not found in /me/accounts")
    if len(pages) == 1:
        return pages[0]
    print("\nSelect a Facebook Page:")
    for idx, page in enumerate(pages, start=1):
        ig = f", IG @{page.ig_username}" if page.ig_username else ", no linked IG"
        print(f"  [{idx}] {page.name} ({page.page_id}{ig})")
    while True:
        choice = input("Enter number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(pages):
            return pages[int(choice) - 1]
        print("Invalid choice, try again.")


def exchange_threads_code(
    *,
    app_id: str,
    app_secret: str,
    code: str,
    port: int,
    client: httpx.Client | None = None,
) -> str:
    """Exchange Threads authorization code for a short-lived access token."""
    data = _graph_post(
        f"{THREADS_OAUTH}/oauth/access_token",
        data={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri(port),
            "code": code,
        },
        client=client,
    )
    token = data.get("access_token")
    if not token:
        raise ValueError(f"Threads code exchange failed: {data}")
    return str(token)


def exchange_threads_long_lived(
    *,
    app_secret: str,
    short_lived_token: str,
    client: httpx.Client | None = None,
) -> str:
    params = {
        "grant_type": "th_exchange_token",
        "client_secret": app_secret,
        "access_token": short_lived_token,
    }
    data = _graph_get(f"{THREADS_OAUTH}/access_token", params=params, client=client)
    token = data.get("access_token")
    if not token:
        raise ValueError(f"Threads long-lived exchange failed: {data}")
    return str(token)


def fetch_threads_profile(*, access_token: str, client: httpx.Client | None = None) -> dict[str, str]:
    params = {"fields": "id,username", "access_token": access_token}
    data = _graph_get(f"{THREADS_GRAPH}/me", params=params, client=client)
    user_id = data.get("id")
    if not user_id:
        raise ValueError(f"Threads /me failed: {data}")
    return {"id": str(user_id), "username": str(data.get("username") or "")}


def _run_oauth_loopback(
    *,
    port: int,
    state: str,
    timeout_seconds: float,
    before_wait: Callable[[], None] | None = None,
) -> OAuthCallbackResult:
    result: OAuthCallbackResult | None = None
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def do_GET(self) -> None:
            nonlocal result
            parsed = urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            qs = parse_qs(parsed.query)
            if qs.get("state", [""])[0] != state:
                result = OAuthCallbackResult(
                    code=None,
                    error="state_mismatch",
                    error_description="OAuth state did not match",
                )
            elif "error" in qs:
                result = OAuthCallbackResult(
                    code=None,
                    error=qs.get("error", [""])[0] or "oauth_error",
                    error_description=qs.get("error_description", [""])[0] or None,
                )
            else:
                result = OAuthCallbackResult(
                    code=qs.get("code", [""])[0] or None,
                    error=None,
                    error_description=None,
                )
            body = b"<html><body><p>ArtistAssist: authorization complete. You can close this tab.</p></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            done.set()

    ssl_context, cert_path, key_path = make_loopback_ssl_context()
    server = HTTPServer(("127.0.0.1", port), Handler)
    server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if before_wait is not None:
            before_wait()
        if not done.wait(timeout=timeout_seconds):
            raise TimeoutError(f"OAuth callback not received within {int(timeout_seconds)}s")
    finally:
        server.shutdown()
        thread.join(timeout=2)
        for path in (cert_path, key_path, cert_path.parent):
            try:
                if path.is_file():
                    path.unlink(missing_ok=True)
                elif path.is_dir():
                    path.rmdir()
            except OSError:
                pass
    if result is None:
        raise RuntimeError("OAuth callback handler did not set a result")
    return result


def obtain_oauth_code(*, auth_url: str, port: int, state: str | None = None) -> str:
    oauth_state = state or secrets.token_urlsafe(24)
    print(f"Listening on {redirect_uri(port)} (self-signed TLS)")
    print("If the browser warns about the certificate, proceed once to finish OAuth.")

    def open_browser() -> None:
        print("Opening browser for authorization…")
        webbrowser.open(auth_url)

    callback = _run_oauth_loopback(
        port=port,
        state=oauth_state,
        timeout_seconds=300.0,
        before_wait=open_browser,
    )
    if callback.error:
        desc = f": {callback.error_description}" if callback.error_description else ""
        raise ValueError(f"OAuth failed ({callback.error}{desc})")
    if not callback.code:
        raise ValueError("OAuth callback missing authorization code")
    return callback.code


def upsert_env_file(env_path: str, updates: dict[str, str]) -> None:
    from pathlib import Path

    path = Path(env_path)
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    remaining = dict(updates)
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if not line or line.lstrip().startswith("#") or "=" not in line:
            out.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in remaining.items():
        if key not in seen:
            if out and out[-1].strip():
                out.append("")
            out.append(f"{key}={value}")
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def validate_facebook_tokens(
    *,
    page_access_token: str,
    page_id: str,
    ig_user_id: str,
    client: httpx.Client | None = None,
) -> None:
    _graph_get(
        f"{FACEBOOK_GRAPH}/{page_id}",
        params={"fields": "id,name", "access_token": page_access_token},
        client=client,
    )
    _graph_get(
        f"{FACEBOOK_GRAPH}/{ig_user_id}",
        params={"fields": "id,username", "access_token": page_access_token},
        client=client,
    )


def validate_threads_token(*, access_token: str, user_id: str, client: httpx.Client | None = None) -> None:
    data = fetch_threads_profile(access_token=access_token, client=client)
    if data["id"] != user_id:
        raise ValueError(f"Threads user id mismatch: env={user_id!r} api={data['id']!r}")


def _graph_get(url: str, *, params: dict[str, Any], client: httpx.Client | None = None) -> dict[str, Any]:
    owns = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        response = http.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and "error" in payload:
            err = payload["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise ValueError(msg or "Graph API error")
        assert isinstance(payload, dict)
        return payload
    finally:
        if owns:
            http.close()


def _graph_post(url: str, *, data: dict[str, str], client: httpx.Client | None = None) -> dict[str, Any]:
    owns = client is None
    http = client or httpx.Client(timeout=30.0)
    try:
        response = http.post(url, data=data)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and "error" in payload:
            err = payload["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise ValueError(msg or "Graph API error")
        assert isinstance(payload, dict)
        return payload
    finally:
        if owns:
            http.close()
