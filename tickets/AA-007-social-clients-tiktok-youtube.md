---
id: AA-007
title: "Social clients: TikTok, YouTube"
status: proposed
priority: P0
type: story
estimate: M
depends_on: [AA-004]
blocks: [AA-008]
refs:
  - PROMPT.md#tiktok-personal-account
  - PROMPT.md#youtube-data-api-v3--youtube-analytics-api
out_of_scope:
  - TikTok publish / inbox drafts / hand-off packages
  - YouTube publishing
  - Prometheus quota metrics (quota shown via API/UI fields only)
---

# AA-007 — Social clients: TikTok, YouTube

## Goal

Implement TikTok Display API (read) and YouTube Data + Analytics (read) adapters with OAuth, sync, and quota tracking surfaced for Settings/Home.

## Context

Completes social read coverage. TikTok has no comments/reach; YouTube has comments + analytics for own channel.

## Deliverables

- [ ] TikTok adapter: profile, stats, public videos + counts; scopes `user.info.basic`, `user.info.stats`, `video.list`
- [ ] Notes for sandbox vs app review in docs
- [ ] YouTube Data API: channel, videos/Shorts + stats, comments
- [ ] YouTube Analytics API: daily views, watch time, subs gained/lost (own channel OAuth)
- [ ] Store daily API quota usage for UI (not Prometheus)
- [ ] Document Google consent screen "In production" requirement for refresh tokens
- [ ] Mocked unit tests

## Acceptance criteria

- [ ] TikTok sync succeeds without comment/reach fields; missing capabilities declared
- [ ] YouTube comments + analytics rows stored when authorized
- [ ] Quota used/remaining (or used) readable via backend API for Settings
- [ ] No publish code paths

## Implementation notes

- Shorts vs long-form: tag format on post records when detectable.
- Analytics granularity: daily rows are enough for context generation.

## Test plan

- Mock Display/Data/Analytics responses → assert DB shape.
- Simulate quota near limit → status field updates.

## Out of scope

Sync orchestration (AA-008), dashboards.
