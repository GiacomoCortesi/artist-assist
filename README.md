# ArtistAssist

Private single-user social media assistant for one musician. Syncs music and social platforms into SQLite, maintains editable LLM-ready artist context, and helps design content (including smart media format adaptations). Publishing happens manually outside the app.

## Quick Start

```bash
cp .env.example .env
make install
make up
```

Open [http://localhost:8080](http://localhost:8080). API health: [http://localhost:8080/api/health](http://localhost:8080/api/health).

Stop the stack with `make down`. See `make help` for all targets.


| Service  | Description                                                | README                         |
| -------- | ---------------------------------------------------------- | ------------------------------ |
| backend  | FastAPI API, adapters, sync scheduler, content agent       | [backend](backend/README.md)   |
| frontend | React/Vite SPA (built to `frontend/dist`, served by Caddy) | [frontend](frontend/README.md) |


With defaults (`PLATFORM_LIVE=0`, `LLM_LIVE=0`), Home → **Refresh sync** uses fixtures; 

Content Studio uses mock drafts. 

For live bootstrap of the app run: 

`make meta-connect`

The command initialize the required social media platform tokens and write them to the app configuration.

## Configuration

Workspace config lives in `[.env.example](.env.example)`. Copy to `.env` before `make up` (Compose loads it for `backend` via `env_file`). Never commit `.env`.

Shared Compose surfaces:


| Surface              | Purpose                                                                                   |
| -------------------- | ----------------------------------------------------------------------------------------- |
| `.env`               | Backend runtime env (see [backend Configuration](backend/README.md#configuration))        |
| `docker-compose.yml` | Project `artistassist`: `backend` (port 8000 internal) + `caddy` (host **8080→80**)       |
| `Caddyfile`          | SPA from `frontend/dist` + reverse proxy `/api/*` → backend                               |
| `VITE_APP_NAME`      | Frontend build-time name (see [frontend Configuration](frontend/README.md#configuration)) |


Offline vs live flags (defaults in `.env.example`):


| Variable        | `0` (default)                               | `1`                                                       |
| --------------- | ------------------------------------------- | --------------------------------------------------------- |
| `PLATFORM_LIVE` | Recorded fixtures under `backend/fixtures/` | Live Spotify/Meta/TikTok/YouTube sync                     |
| `LLM_LIVE`      | Deterministic mock drafts in Content Studio | Live OpenAI/Anthropic chat (`OPENAI_LIVE` still accepted) |


