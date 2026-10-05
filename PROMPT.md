# ArtistAssist MVP — Autonomous implementation brief

You are an autonomous coding agent (e.g. Claude Fable). Your job is to **implement and test the entire ArtistAssist MVP** by completing every ticket under `tickets/` end-to-end, without waiting for human confirmation between tickets.

Standing project context and rationale: [`AGENTS.md`](AGENTS.md) (read it first on every session).  
This file is product + process truth for a full MVP build. Individual tickets under `tickets/` are the executable work units. If a detail conflicts, **ticket acceptance criteria win for that ticket’s scope**; this file wins for global out-of-scope and **Fable build-efficiency** rules; `AGENTS.md` wins for day-to-day conventions.

---

## Mission

Build **ArtistAssist** (tagline: "Your social media assistant"): a private, single-user web app for one musician.

**In scope**

1. **Information retrieval** — sync social + music data into SQLite and expose a complete, meaningful artist library + LLM-ready context (the user’s custom information).
2. **Content agent** — help **design and prepare content in general** (single posts, series, campaigns, captions, hashtags, media adaptations), always grounded on the synced artist data, context docs, releases, and tone of voice. Does **not** publish to platforms.

**Out of scope (never implement)**

- Publishing / scheduling / hand-off upload to platforms
- Statistics dashboard, Recharts analytics, Prometheus / `/metrics` / Grafana
- MusicBrainz, Last.fm
- Multi-user auth (access = Tailscale on the host)

Name everything consistently: **ArtistAssist** in UI/titles/README/User-Agent; Compose project `artistassist`.

---

## How you work (mandatory)

### Source of work

1. Read `AGENTS.md`, `tickets/README.md`, `tickets/_SCHEMA.md`, then tickets **AA-001 → AA-015** in dependency order.
2. For each ticket: read the full markdown file → implement deliverables → run that ticket’s test plan → mark acceptance criteria `[x]` → set `status: done` → add a short **Done notes** section → commit only if the human later asks (do not invent git policy; prefer leaving a clean tree and a progress log).
3. Keep a running progress file: `tickets/PROGRESS.md` with date, ticket id, pass/fail, commands run, blockers.

### Autonomy rules

- **Do not stop** between tickets to ask permission. Only stop if blocked by missing live credentials that cannot be mocked — then implement fixtures/mocks, document real OAuth setup in README, and continue.
- Prefer **mocked/recorded HTTP fixtures** so the full suite runs offline. Live API calls are optional and must be behind env flags defaulting to off.
- After each ticket (or parallel batch), run relevant tests. Before declaring MVP done, run full `make test` / `make lint` / `make build` (or create these targets in AA-001 and keep them green).
- Never expand scope into out-of-scope rows above “while you’re here”.
- Keep the MVP simple: one user, SQLite, in-process sync scheduler, no microservices.

### Suggested execution order

Respect `depends_on`. Where independent, you may parallelize:

| Phase | Tickets | Notes |
| --- | --- | --- |
| 1 Foundation | AA-001 | Skeleton first |
| 2 Parallel | AA-002 \|\| AA-003 | Brand + data layer |
| 3 Interface | AA-004 | Adapter contract |
| 4 Parallel clients | AA-005 \|\| AA-006 \|\| AA-007 | Music + Meta + TikTok/YouTube |
| 5 Pipeline | AA-008 → AA-009 | Sync → context |
| 6 UI | AA-011 \|\| AA-012 | Home/Settings + Library/Context |
| 7 Agent | AA-013 → AA-014 | Content agent backend then Studio UI |
| 8 Ship | AA-015 | Hardening, fixtures, README |

Done when **all tickets AA-001…AA-015 (AA-010 removed)** are `status: done`, tests pass offline, and README walkthrough works with fixtures.

### Definition of “MVP complete”

- [ ] All tickets `done` with criteria checked
- [ ] `make test`, `make lint`, `make build` succeed without live platform/OpenAI keys
- [ ] App boots via Docker Compose / Makefile; Home loads
- [ ] Grep audit: no prometheus metrics pipeline, no MusicBrainz/Last.fm clients, no publish/schedule APIs
- [ ] `tickets/PROGRESS.md` summarizes the run

---

## Fable / coding-agent build efficiency (not product OpenAI cost)

These rules exist only to **reduce the cost and length of the autonomous implementation run** (your own context, tools, and retries). They are **not** product requirements to cheapen the app’s OpenAI API usage at runtime. Ship a capable content agent and media pipeline; do not gut features for “API savings.”

While implementing:

- Do **not** call live OpenAI or social APIs to explore during coding. Use mocks, VCR/cassette fixtures, and deterministic fakes so CI stays offline.
- For image/media tests: one small fixture image + Pillow transforms is enough; do not loop real image-generation APIs while developing.
- Prefer reading `AGENTS.md`, ticket files, and this brief over re-deriving requirements.
- Implement **ticket scope only**; avoid speculative refactors and extra epics.
- Cap exploratory spikes: if stuck >30 minutes on an OAuth nuance, ship a documented stub + fixture path and continue.
- Keep `PROGRESS.md` short (bullet status), not essay-length.
- Reuse shared adapter/test helpers once; don’t copy-paste a new harness per platform.

---

## Product requirements (summary for tickets)

### Tech stack

- Frontend: React + Vite + TypeScript, Tailwind CSS v4, shadcn/ui, Motion, Lucide, Simple Icons, Sonner, Geist Sans/Mono (Fontsource).
- Backend: Python + FastAPI.
- Storage: SQLite (posts, comments, media library, music, tags, drafts, content plans, context, encrypted tokens, sync jobs).
- LLM: OpenAI or Anthropic (Claude) for chat via `LLM_PROVIDER` in `.env`; OpenAI image model for generate/edit when the user asks.
- Media: Pillow (and optional smart-crop helpers) for **autocrop / resize / safe-area adaptations** across platform formats; OpenAI image model for generate/edit when the user asks. Optional Cloudflare R2; default local disk for assets.
- Scheduler: in-process (e.g. APScheduler) for **data sync only**.
- Packaging: Docker Compose (`caddy`, `backend`), Makefile. Tailscale on host.

### Brand & UI

- Minimal B/W + vermilion accent ≈ `#FF4D2E` (OKLCH CSS variables / shadcn tokens).
- AA monogram SVG (`currentColor`), assets in `frontend/public/brand/`, PWA manifest, `docs/design.md`, `/styleguide`.
- System/Light/Dark theme; mobile-first; sidebar desktop / bottom tabs mobile.
- Empty/loading/error states designed. No stats charts. Neutral device-style format previews (not platform UI clones).

### Security & config

- No in-app auth. Secrets in `.env`; runtime tokens encrypted in SQLite.
- Secrets never in frontend, logs, LLM prompts, or git.
- Static artist links editable in Settings.

### Adapters (read-only)

Common interface + Pydantic models. Official APIs only. Capability flags: publish always false.

| Source | Ticket | Role |
| --- | --- | --- |
| Spotify | AA-005 | Primary catalog |
| SoundCloud | AA-005 | Tracks/playlists/engagement |
| Deezer | AA-005 | Fans + cross-check |
| Instagram, Facebook, Threads | AA-006 | Posts/comments/insights |
| TikTok, YouTube | AA-007 | Videos + YT comments/analytics |

Merge music by normalized title+date; Spotify authoritative for catalog metadata. No MusicBrainz/Last.fm.

### Sync (AA-008)

Daily + manual refresh. Tag untagged posts (taxonomy) and comments (sentiment/theme). Merge music. Regenerate context. Partial success if one platform fails.

### Context (AA-009)

Markdown + YAML front matter: `artist_profile.md`, `platform_<name>.md`. Section locks. Keep `artist_profile.md` compact enough for reliable agent grounding (target ~≤2,000 tokens for the core profile).

### Content agent & media (AA-013 / AA-014)

The Content Studio agent is a **general content co-designer**, not a campaign-only wizard. It must leverage **all** user custom information: artist context docs, synced posts/comments, music catalog, tone of voice, goals, and the **media library**.

Capabilities (non-exhaustive):

- Ideate and draft any content: single post, carousel, story/reel concept, thread, YouTube description, promo for a release, or a multi-post plan when useful.
- Write/adapt copy and hashtags per platform in the artist’s voice.
- **Manage user media:** upload/import, browse library (including synced post media where available), attach assets to drafts.
- **Smart format adaptation:** from an original image (or generated/edited master), produce platform-ready variants with smart autocrop / focal-point / face-aware crop when possible, plus deterministic Pillow resize. Support at least: feed 4:5, square 1:1, story/reel 9:16, landscape 16:9 (YouTube/Facebook), and document per-platform safe margins where relevant.
- Let the user refine crop (focal point / manual adjust) and regenerate variants.
- Export/copy packages (caption + hashtags + adapted media) for manual publishing outside the app.

Constraints: ground on real context; never invent dates/links/metrics; never claim content was published; **no Publish / Schedule** UI or APIs.

### Pages

| Page | Ticket |
| --- | --- |
| Home, Settings | AA-011 |
| Artist library, Context | AA-012 |
| Content Studio | AA-014 (UI) + AA-013 (agent + media pipeline) |
| Styleguide | AA-002 |

### Deployment (AA-015)

Compose project `artistassist`; Makefile; README with OAuth setup, fixture mode, first sync, Content Studio walkthrough; Tailscale notes.

---

## Ticket map (do not invent extra epics)

| ID | File | Focus |
| --- | --- | --- |
| AA-001 | `tickets/AA-001-project-skeleton.md` | Compose, Makefile, FastAPI, Vite shells |
| AA-002 | `tickets/AA-002-brand-design-system.md` | Brand, theme, shell chrome, styleguide |
| AA-003 | `tickets/AA-003-data-layer.md` | SQLite schema, encrypted tokens, media library |
| AA-004 | `tickets/AA-004-adapter-interface.md` | Read-only adapter contract |
| AA-005 | `tickets/AA-005-music-clients.md` | Spotify, SoundCloud, Deezer + merge |
| AA-006 | `tickets/AA-006-social-clients-meta.md` | IG, Facebook, Threads |
| AA-007 | `tickets/AA-007-social-clients-tiktok-youtube.md` | TikTok, YouTube |
| AA-008 | `tickets/AA-008-sync-orchestration.md` | Scheduler, tagging, status APIs |
| AA-009 | `tickets/AA-009-artist-context.md` | Context markdown generation |
| AA-011 | `tickets/AA-011-settings-home.md` | Settings + Home |
| AA-012 | `tickets/AA-012-library-context-ui.md` | Library + Context UI |
| AA-013 | `tickets/AA-013-content-studio-agent.md` | Content agent + smart media adaptations |
| AA-014 | `tickets/AA-014-content-studio-ui.md` | Content Studio UI + media previews |
| AA-015 | `tickets/AA-015-hardening-docs.md` | Fixtures, README, audits |

---

## Start now

1. Create `tickets/PROGRESS.md`.
2. Implement **AA-001** fully (tests green).
3. Continue through **AA-015** per the phase table.
4. Finish with the MVP-complete checklist above.

Do not implement publishing, statistics, Prometheus, MusicBrainz, or Last.fm.
