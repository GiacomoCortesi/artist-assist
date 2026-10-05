# AGENTS.md — ArtistAssist

Guidance for AI coding agents working in this repository.  
Full autonomous MVP build brief: [`PROMPT.md`](PROMPT.md).  
Executable work units: [`tickets/`](tickets/).

User chat instructions always override this file.

---

## Project overview

**ArtistAssist** (“Your social media assistant”) is a **private, single-user** web app for one musician.

It does two jobs:

1. **Know the artist** — sync social platforms (Instagram, Facebook, Threads, TikTok, YouTube) and music platforms (Spotify, SoundCloud, Deezer) into SQLite, and maintain an editable, LLM-ready context of the user’s custom information (music, tone, audience, history).
2. **Design content** — a specialized agent helps prepare and design **content in general** (posts, series, campaigns, copy, media), leveraging that context. Includes **smart autocrop / format adaptation** of the user’s media for each social format. The musician publishes **manually outside the app**.

It is **not** a multi-tenant SaaS, analytics suite, or social publisher.

---

## Why this product exists (rationale)

Musicians already have scattered identity across platforms. Generic AI chat tools lack *their* releases, tone, comments, and upcoming gigs. ArtistAssist centralizes that signal so content work starts from the real artist, not a blank prompt.

**MVP bets**

| Choice | Rationale |
| --- | --- |
| Design + export, not publish | Publishing APIs and app-review complexity dominate scope; value is on-brand content and platform-ready media. Manual post is fine for one user. |
| General content agent (not campaign-only) | Campaigns are one use case. The agent must help with any content task using the full personal context. |
| Smart media adaptations | Each platform needs different ratios/safe areas; automating crop/resize from one master asset is core utility. |
| No statistics dashboard / Prometheus | Charts and metrics pipelines are a second product. Performance fields may inform *context text*, not a dashboard. |
| Spotify + SoundCloud + Deezer (not MusicBrainz / Last.fm) | Prefer APIs the musician already uses; Spotify is catalog authority. |
| Single user + Tailscale | Auth/orgs/billing out of scope; network access control is enough. |
| SQLite + one backend | One operator, private deploy; avoid distributed complexity. |
| Read-only platform adapters | Same sync interface; publish flags stay false for MVP. |
| LLM-ready markdown context | Stable grounding for the content agent; humans can lock/edit sections. |

---

## Document map

| Doc | Role |
| --- | --- |
| `AGENTS.md` (this file) | Standing context, rationale, conventions for any agent session |
| `PROMPT.md` | Autonomous “build the whole MVP” brief: order, Fable build-efficiency rules, completion checklist |
| `tickets/AA-*.md` | Per-feature scope, deliverables, acceptance criteria, tests |
| `tickets/README.md` | Sprint order and dependency table |
| `tickets/_SCHEMA.md` | Ticket front-matter contract |
| `tickets/PROGRESS.md` | Agent-written run log (create if missing) |
| `docs/design.md` | Brand tokens / logo rules (created in AA-002) |
| `README.md` | Human setup (created/finished in AA-001 / AA-015) |

**Conflict rule:** ticket acceptance criteria win for that ticket’s scope; `PROMPT.md` wins for global out-of-scope and Fable build-efficiency; this file wins for day-to-day conventions unless the user says otherwise.

---

## Architecture (target)

```
Browser (React/Vite) ──► Caddy ──► FastAPI
                              │
                              ▼
                           SQLite
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  Platform adapters     Sync scheduler      Content agent
  (read-only)           (daily+manual)      + media pipeline
                                              (autocrop/adapt)
```

- **Frontend:** React + Vite + TypeScript, Tailwind v4, shadcn/ui, Motion, Lucide, Simple Icons, Sonner, Geist via Fontsource.
- **Backend:** Python + FastAPI; in-process scheduler (e.g. APScheduler) for **sync only**.
- **Media pipeline:** library of originals + derived variants; smart autocrop / focal-point / face-aware when available; Pillow for deterministic resize/safe-area; OpenAI image for generate/edit on request; chat via OpenAI or Anthropic (Claude); optional R2, default local disk.
- **Deploy:** Docker Compose project name `artistassist` (`caddy`, `backend`); Tailscale on the host.

Expected layout (after AA-001+):

- `backend/` — API, adapters, sync, context, agent, media processing
- `frontend/` — SPA
- `tickets/` — backlog
- `docs/` — design and adapter notes
- `.env.example` — secrets template (never commit `.env`)

---

## Hard constraints (do not violate)

- No publish / schedule / hand-off upload to social platforms.
- No statistics dashboard, Recharts analytics product, Prometheus `/metrics` pipeline.
- No MusicBrainz or Last.fm clients.
- No scraping; official APIs only.
- Secrets and tokens never in frontend, logs, LLM prompts, or git. Encrypt runtime tokens at rest.
- Name: **ArtistAssist** in UI; Compose/`User-Agent`: `artistassist` / `ArtistAssist/<version>`.

---

## Fable / coding-agent build efficiency

When running the full MVP via `PROMPT.md`, optimize **your own** run (context, retries, live API calls during development). Use fixtures/mocks for CI and implementation. Do not remove media quality or agent capability to “save API tokens.”

Details: `PROMPT.md` → “Fable / coding-agent build efficiency”.

---

## How to work in this repo

1. Read this file, then the relevant `tickets/AA-*.md` (and `PROMPT.md` if doing a full MVP run).
2. Implement only the ticket (or user-asked) scope; update ticket checkboxes and `status` when done.
3. Prefer small, reviewable changes; match existing patterns once code exists.
4. Add or extend **mocked** tests with every adapter/API/media path.
5. Run `make test` / `make lint` / `make build` when those targets exist; fix failures before moving on.
6. Do not commit unless the user asks.

### Naming & style

- TypeScript: strict; imports at top of file (no inline imports).
- Python: typed where practical; Pydantic at API/adapter boundaries; raise errors, never return failure as success.
- Exhaustive `switch` / unions: handle `never` in default where applicable.
- UI: mobile-first; vermilion accent sparingly; designed empty/loading/error states; no Publish/Schedule controls anywhere.

### Security checklist before finishing a task

- [ ] No secrets in source or fixtures that look like real keys
- [ ] Tokens redacted in logs
- [ ] OAuth scopes are read-only as listed in tickets
- [ ] Frontend cannot trigger platform publish

---

## Autonomous full-MVP runs

If instructed to implement the whole application: follow **`PROMPT.md`** exactly (phases AA-001→AA-015, `PROGRESS.md`, offline tests, completion checklist). Do not invent extra epics (publisher, Grafana, multi-user, MusicBrainz, etc.).

---

## Quick “what good looks like”

A musician opens Home → sees connection/sync status → edits Context → uses Content Studio to design any content (from a single caption to a multi-post plan), adapts media to IG/TikTok/YouTube/etc. formats with smart crops, then **downloads/copies** a package and posts it themselves.
