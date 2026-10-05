---
id: AA-011
title: Settings + Home pages
status: proposed
priority: P0
type: story
estimate: M
depends_on: [AA-002, AA-008]
blocks: [AA-015]
refs:
  - PROMPT.md#1-home
  - PROMPT.md#6-settings
out_of_scope:
  - Statistics tiles / charts
  - Publish / schedule counts (use open drafts / export-ready counts only)
---

# AA-011 — Settings + Home pages

## Goal

Implement Home and Settings as the operational surfaces: connection health, sync controls, artist identity confirmation, taxonomy, model defaults.

## Context

Home orients the musician; Settings wires platforms and music IDs. No stats dashboard.

## Deliverables

### Home

- [ ] Logo, tagline, greeting
- [ ] Cards to Library, Context, Events, Content Studio, Settings
- [ ] Per platform + music source: connection status, token expiry, last sync
- [ ] Next upcoming event
- [ ] Counts: open content drafts + items ready to export
- [ ] Manual Refresh sync action + toast feedback

### Settings

- [ ] Connect/reconnect flows + expiry display for each platform
- [ ] Music identity lookup/confirm (Spotify, SoundCloud, Deezer)
- [ ] Topic taxonomy editor
- [ ] Chat/image model display (from `.env`, optional override if implemented)
- [ ] Sync schedule display + manual refresh
- [ ] Editable static artist links (website, ticket shop, extras)

## Acceptance criteria

- [ ] Home never shows Prometheus-backed or chart panels
- [ ] Disconnected platform shows clear CTA (Reconnect)
- [ ] Confirmed music IDs visible; search prevents same-name mix-ups
- [ ] No Publish / Schedule controls
- [ ] Loading/empty/error states match design system

## Implementation notes

- Wire to APIs from AA-005–AA-008; stub counts at 0 until AA-013/014 persist drafts.
- Command palette can deep-link these pages.

## Test plan

- Mock API statuses → Home cards reflect connected/expired/error.
- Confirm Spotify artist → Settings shows ID; Library later reads same ID.

## Out of scope

Library/Context content (AA-012), Studio (AA-014).
