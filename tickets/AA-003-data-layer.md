---
id: AA-003
title: SQLite data layer & encrypted tokens
status: proposed
priority: P0
type: story
estimate: L
depends_on: [AA-001]
blocks: [AA-004, AA-010]
refs:
  - PROMPT.md#tech-stack
  - PROMPT.md#configuration-and-security
out_of_scope:
  - Prometheus metric tables
  - Publish job / schedule tables
  - MusicBrainz / Last.fm identity fields
---

# AA-003 — SQLite data layer & encrypted tokens

## Goal

Define SQLite as source of truth with migrations/models for accounts, posts, comments, music entities, tags, drafts, content plans, events, context documents, sync jobs, encrypted runtime tokens, and a **media library** (originals + derived platform variants / crop metadata).

## Context

All sync, context, and agent features read/write here. Tokens must never be plaintext at rest.

## Deliverables

- [ ] Migration or schema bootstrap approach (document choice: Alembic / raw SQL / SQLModel — pick one)
- [ ] Tables/models for:
  - platform accounts + connection status
  - posts, comments (synced social media references)
  - media library: originals, derived variants (format preset, crop box, focal point), optional link to source post
  - music artists / releases / tracks (Spotify, SoundCloud, Deezer source fields)
  - topic taxonomy + post topic tags; comment sentiment/theme
  - events + event suggestions
  - context documents + per-section manual locks
  - content drafts + optional multi-post plans + prepared asset metadata
  - sync run history / job state
  - encrypted OAuth/runtime tokens
- [ ] Token encrypt/decrypt helper using key from `.env`
- [ ] Repository/DAO layer thin enough for FastAPI routes and sync jobs
- [ ] Unit tests for encryption round-trip and basic CRUD

## Acceptance criteria

- [ ] Fresh DB creates cleanly on backend start (or via `make` target)
- [ ] Tokens stored ciphertext only; decrypt only in backend memory
- [ ] Schema has **no** publish-queue / scheduled-publish entities
- [ ] Music identity columns support Spotify / SoundCloud / Deezer IDs only (no MBID / Last.fm)
- [ ] Tests pass without network

## Implementation notes

- Prefer explicit `source` enums: `spotify | soundcloud | deezer | instagram | facebook | threads | tiktok | youtube`.
- Soft-delete optional; keep MVP simple.

## Test plan

- Run migrations → insert fixture row of each major entity → query back.
- Encrypt token → restart process → decrypt equals original.

## Out of scope

Adapters, sync jobs, UI.
