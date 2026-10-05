# Meta token setup (live sync)

ArtistAssist syncs Instagram, Facebook Page, and Threads using **read-only** Graph
API scopes. Publish scopes are never requested.

## Prerequisites

- Meta developer app with `META_APP_ID` and `META_APP_SECRET` in `.env`
- Facebook Page you admin
- Instagram Professional account linked to that Page
- (Optional) Threads API use case on the same or linked app
- App in **Development** mode: your Facebook/Instagram/Threads accounts must be
  app testers/roles

## One-time app configuration

## One-time app configuration

In Meta Developer Console → your app:

1. **Settings → Basic → App Domains** — add:
   ```text
   localhost
   ```
   (Do **not** put `127.0.0.1` here — Meta rejects raw IPs and shows “domain not included”.)

2. **Settings → Basic → Website** (add platform if missing) → Site URL:
   ```text
   https://localhost:8765/
   ```

3. **Facebook Login → Settings → Valid OAuth Redirect URIs** — add exactly:
   ```text
   https://localhost:8765/callback
   ```

Meta requires HTTPS for Login (“Enforce HTTPS”). The CLI serves a **self-signed**
TLS cert on that port; your browser may warn once — proceed to finish OAuth.

For Threads, register the same redirect URI on the Threads use case settings.

This URI is for the local `make meta-connect` CLI only. It is separate from
`META_REDIRECT_URI` on port 8080 (reserved for a future in-app OAuth flow).

## Connect (recommended)

From the repo root:

```bash
make meta-connect
```

Optional: limit which Meta services to authorize (default `all`):

```bash
make meta-connect SERVICES=fb,instagram   # skip Threads
make meta-connect SERVICES=threads        # Threads only
make meta-connect SERVICES=ig             # Facebook Login for IG (shared Page OAuth)
```

Aliases: `facebook`/`fb`, `instagram`/`ig`, `threads`, or `all`.

Facebook and Instagram share one Login (Page + linked IG). Threads is a second browser pass.

Flow for selected services:

1. Short-lived user token via localhost OAuth callback
2. Long-lived token exchange
3. Page pick + linked IG Business account discovery (when fb/ig selected)
4. Threads long-lived token + user id (when threads selected)
5. Upserts keys into `.env` (disable with `make meta-connect WRITE_ENV=0`)

Then enable live sync:

```env
PLATFORM_LIVE=1
```

Restart the backend (`make down && make up` or restart uvicorn). On startup,
tokens are copied from `.env` into encrypted SQLite storage.

## Read scopes requested

**Facebook / Instagram**

- `pages_show_list`
- `business_management` (needed so `/me/accounts` returns Pages linked to Meta Business Suite)
- `pages_read_engagement`
- `pages_read_user_content`
- `instagram_basic`
- `instagram_manage_comments`
- `instagram_manage_insights`

**Threads**

- `threads_basic`
- `threads_read_replies`

## Manual fallback

If browser OAuth is unavailable, pass short-lived tokens from Graph API Explorer:

```bash
cd backend
.venv/bin/python scripts/meta_token_bootstrap.py \
  --token "SHORT_FB_USER_TOKEN" \
  --threads-token "SHORT_THREADS_TOKEN" \
  --write-env
```

## Validate

```bash
cd backend && .venv/bin/python scripts/meta_token_bootstrap.py --check
```

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Browser says “authorization complete” then CLI errors | Normal — browser only confirms OAuth callback; token/page steps run after |
| Empty `/me/accounts` | Page is under Meta Business Suite but token lacks `business_management`; or Page unchecked in Login; Dev mode without app role; `pages_show_list` declined |
| No linked IG on Page | Link IG Business/Creator account to Page in Meta Business settings |
| Redirect URI mismatch | Add exact `https://localhost:8765/callback` under Facebook Login → Settings |
| Domain not included / Impossibile caricare l'URL | Add `localhost` under Settings → Basic → App Domains (not `127.0.0.1`) |
| Insecure connection / HTTPS error | Use the `https://localhost` redirect URI; accept self-signed cert warning |
| Sync still shows fixtures | `PLATFORM_LIVE=0` — set to `1` and restart |
| Home shows connected but wrong data | Old fixture rows — run Refresh sync after live bootstrap |

See also [`meta-insights.md`](meta-insights.md) for insight metric caveats.
