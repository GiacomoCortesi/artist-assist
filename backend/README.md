# ArtistAssist backend

FastAPI service: platform adapters (read-only), sync scheduler, artist context, content agent, and media pipeline. Tokens are encrypted at rest; publish/schedule capabilities stay off.

API-only local run (from `backend/`, with venv activated):

```bash
make run
```

Listens on `http://0.0.0.0:8000`. Tests and lint: `make test`, `make lint`.

Meta live token bootstrap (writes keys into root `.env` when `WRITE_ENV=1`):

```bash
make meta-connect
# optional: SERVICES=fb,ig,threads WRITE_ENV=0 make meta-connect
```

Validate bootstrap: `.venv/bin/python scripts/meta_token_bootstrap.py --check` (from `backend/`).

## Configuration

Loads environment from the process env and `.env` (see root [`.env.example`](../.env.example)). Compose mounts volumes for SQLite data and media storage.

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `APP_NAME` | Application display name | `ArtistAssist` | optional |
| `APP_VERSION` | Version string / User-Agent | `0.1.0` | optional |
| `ENVIRONMENT` | Runtime environment label | `development` | optional |
| `LOG_LEVEL` | Log level | `INFO` | optional |
| `BACKEND_HOST` | Bind host | `0.0.0.0` | optional |
| `BACKEND_PORT` | Bind port | `8000` | optional |
| `DATABASE_URL` | SQLite URL | `sqlite:///./data/artistassist.db` | optional |
| `MEDIA_ROOT` | Local media storage path | `./storage` | optional |
| `TOKEN_ENCRYPTION_KEY` | Encrypts OAuth tokens at rest | `change-me-to-a-32-byte-url-safe-base64-key` | **required in production** (change default) |
| `LLM_PROVIDER` | Chat provider: `openai` or `anthropic` | `openai` | optional |
| `LLM_LIVE` | `1` = live LLM; `0` = mock (`OPENAI_LIVE` alias) | `0` | optional |
| `OPENAI_API_KEY` | OpenAI API key | _(empty)_ | required when `LLM_LIVE=1` and provider is openai |
| `OPENAI_CHAT_MODEL` | OpenAI chat model | `gpt-4o-mini` | optional |
| `OPENAI_IMAGE_MODEL` | OpenAI image model | `gpt-image-1` | optional |
| `ANTHROPIC_API_KEY` | Anthropic API key | _(empty)_ | required when `LLM_LIVE=1` and provider is anthropic |
| `ANTHROPIC_CHAT_MODEL` | Anthropic chat model | `claude-sonnet-4-6` | optional |
| `PLATFORM_LIVE` | `1` = live platform APIs; `0` = fixtures | `0` | optional |
| `FIXTURE_MODE` | Force fixtures when set (`1`/`0`); overrides `PLATFORM_LIVE` | _(unset)_ | optional |
| `SPOTIFY_CLIENT_ID` | Spotify OAuth client id | _(empty)_ | for live Spotify |
| `SPOTIFY_CLIENT_SECRET` | Spotify OAuth secret | _(empty)_ | for live Spotify |
| `SPOTIFY_REDIRECT_URI` | Spotify OAuth redirect | `http://localhost:8080/api/oauth/spotify/callback` | optional |
| `SOUNDCLOUD_CLIENT_ID` | SoundCloud OAuth client id | _(empty)_ | for live SoundCloud |
| `SOUNDCLOUD_CLIENT_SECRET` | SoundCloud OAuth secret | _(empty)_ | for live SoundCloud |
| `SOUNDCLOUD_REDIRECT_URI` | SoundCloud OAuth redirect | `http://localhost:8080/api/oauth/soundcloud/callback` | optional |
| `DEEZER_APP_ID` | Deezer app id | _(empty)_ | for live Deezer |
| `DEEZER_APP_SECRET` | Deezer app secret | _(empty)_ | for live Deezer |
| `DEEZER_REDIRECT_URI` | Deezer OAuth redirect | `http://localhost:8080/api/oauth/deezer/callback` | optional |
| `META_APP_ID` | Meta app id | _(empty)_ | for live Meta |
| `META_APP_SECRET` | Meta app secret | _(empty)_ | for live Meta |
| `META_REDIRECT_URI` | Meta OAuth redirect (in-app) | `http://localhost:8080/api/oauth/meta/callback` | optional |
| `META_PAGE_ACCESS_TOKEN` | Page token (e.g. from `make meta-connect`) | _(empty)_ | for live Meta sync |
| `META_PAGE_ID` | Facebook Page id | _(empty)_ | for live Meta sync |
| `META_IG_USER_ID` | Instagram user id | _(empty)_ | for live IG sync |
| `THREADS_ACCESS_TOKEN` | Threads user token | _(empty)_ | for live Threads |
| `THREADS_USER_ID` | Threads user id | _(empty)_ | for live Threads |
| `TIKTOK_CLIENT_KEY` | TikTok client key | _(empty)_ | for live TikTok |
| `TIKTOK_CLIENT_SECRET` | TikTok client secret | _(empty)_ | for live TikTok |
| `TIKTOK_REDIRECT_URI` | TikTok OAuth redirect | `http://localhost:8080/api/oauth/tiktok/callback` | optional |
| `YOUTUBE_CLIENT_ID` | Google/YouTube OAuth client id | _(empty)_ | for live YouTube |
| `YOUTUBE_CLIENT_SECRET` | Google/YouTube OAuth secret | _(empty)_ | for live YouTube |
| `YOUTUBE_REDIRECT_URI` | YouTube OAuth redirect | `http://localhost:8080/api/oauth/youtube/callback` | optional |
| `R2_ACCOUNT_ID` | Cloudflare R2 account | _(empty)_ | optional (local disk default) |
| `R2_ACCESS_KEY_ID` | R2 access key | _(empty)_ | optional |
| `R2_SECRET_ACCESS_KEY` | R2 secret | _(empty)_ | optional |
| `R2_BUCKET` | R2 bucket name | _(empty)_ | optional |
| `R2_PUBLIC_BASE_URL` | Public base URL for R2 objects | _(empty)_ | optional |
| `SYNC_CRON_HOUR` | Daily sync hour (UTC-style cron hour) | `3` | optional |
| `SYNC_CRON_MINUTE` | Daily sync minute | `0` | optional |

OAuth redirect URIs above must match provider app settings when using live mode via Caddy on port 8080. Meta connect script uses a local HTTPS callback (`https://localhost:8765/callback`) — see [docs/meta-tokens.md](../docs/meta-tokens.md).

Dockerfile defaults: `DATABASE_URL`, `MEDIA_ROOT=./storage`, `PLATFORM_LIVE=0`. Healthcheck hits `/api/health`.
