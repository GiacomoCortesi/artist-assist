---
id: AA-012
title: Artist library + Context UI
status: proposed
priority: P0
type: story
estimate: L
depends_on: [AA-002, AA-009, AA-010]
blocks: [AA-015]
refs:
  - PROMPT.md#2-artist-library-information-retrieval
  - PROMPT.md#3-context
out_of_scope:
  - Chart-heavy analytics / statistics dashboard
  - Publishing actions
---

# AA-012 — Artist library + Context UI

## Goal

Ship information-retrieval UI: browse synced artist world (music + posts + themes) and edit/regenerate LLM context documents.

## Context

MVP focus #1 is complete, meaningful artist information — this ticket is that surface.

## Deliverables

### Artist library

- [ ] Profile + music identity (Spotify / SoundCloud / Deezer badges & IDs)
- [ ] Merged releases/tracks with source badges and "no data" states
- [ ] Recent posts per platform (caption, thumbs, sample comments)
- [ ] Topic taxonomy overview + comment sentiment themes (content-first, not charts)
- [ ] Static links section
- [ ] Search/filter where useful

### Context

- [ ] List documents with source + last generated_at
- [ ] Section editor with lock indicator
- [ ] Actions: regenerate all / one; keep manual vs overwrite
- [ ] Read-only preview of markdown

## Acceptance criteria

- [ ] Library remains usable if one music source has no data
- [ ] Locked context sections visually distinct and preserved on regen
- [ ] No Recharts / growth tiles / heatmaps
- [ ] Empty/loading/error states complete
- [ ] Mobile layout usable

## Implementation notes

- Prefer lists and detail sheets over card-heavy dashboards.
- Platform logos via Simple Icons only as small icons.

## Test plan

- Seed DB → Library shows releases + posts.
- Edit+lock section → regenerate → text retained.

## Out of scope

Agent chat UI (AA-014).
