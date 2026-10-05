---
id: AA-006
title: "Social clients: Instagram, Facebook, Threads"
status: proposed
priority: P0
type: story
estimate: L
depends_on: [AA-004]
blocks: [AA-008]
refs:
  - PROMPT.md#instagram-graph-api-via-facebook-login
  - PROMPT.md#facebook-graph-api-page
  - PROMPT.md#threads-threads-api
out_of_scope:
  - Content publishing permissions or APIs
  - pages_manage_posts / instagram_content_publish / threads_content_publish
  - Statistics dashboard
---

# AA-006 — Social clients: Instagram, Facebook, Threads

## Goal

Implement Meta read clients for Instagram, Facebook Page, and Threads: OAuth/token storage, refresh where applicable, sync profile/posts/comments/insights into SQLite.

## Context

Core social corpus for tone-of-voice, topics, and agent grounding. Read-only MVP.

## Deliverables

- [ ] Instagram Graph adapter: profile, media, insights (`total_value` where required), comments
- [ ] Facebook Page adapter: posts, comments, post/page insights (current metric names + mapping doc)
- [ ] Threads adapter: profile, posts, replies-as-comments, insights; auto-refresh long-lived tokens before 60-day expiry
- [ ] OAuth/connect endpoints or documented token bootstrap for single-user setup
- [ ] Persist connection status + token expiry for UI
- [ ] UI caveats for Threads (insights pre-2024-06-01; top-level replies only) exposed via API flags
- [ ] Mocked unit tests per adapter

## Acceptance criteria

- [ ] Sync stores posts/media/comments without requiring publish scopes
- [ ] Token refresh path tested (or clearly documented + manual refresh) for Threads
- [ ] Errors log platform code + trace id, never tokens
- [ ] Capability flags: read yes, publish no
- [ ] Insight metric renames documented in `docs/meta-insights.md`

## Implementation notes

- One Meta app shared IG+FB; separate Threads use case/credentials as per prompt.
- Prefer minimal scopes listed in PROMPT.md.

## Test plan

- Replay recorded Graph responses → DB rows.
- Expired token → refresh or clear error surfaced on connection status.

## Out of scope

TikTok/YouTube (AA-007), tagging (AA-008), UI (AA-011/012).
