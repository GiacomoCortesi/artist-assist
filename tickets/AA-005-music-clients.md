---
id: AA-005
title: "Music clients: Spotify, SoundCloud, Deezer + merge"
status: proposed
priority: P0
type: story
estimate: L
depends_on: [AA-004]
blocks: [AA-008]
refs:
  - PROMPT.md#music-data-sources
out_of_scope:
  - MusicBrainz
  - Last.fm
  - Statistics exposition of fans/listeners
  - Publishing
---

# AA-005 — Music clients: Spotify, SoundCloud, Deezer + merge

## Goal

Implement read clients for Spotify (primary catalog), SoundCloud, and Deezer; identity search/confirm; catalog sync into SQLite; merge/dedupe releases and genres.

## Context

Music identity drives artist context. Spotify is authoritative for catalog metadata.

## Deliverables

- [ ] Spotify client (Client Credentials for public catalog; document if user OAuth needed later)
- [ ] SoundCloud client (official API)
- [ ] Deezer client (public API)
- [ ] Settings API: search-by-name per source + confirm & store IDs
- [ ] Sync job steps: profile, releases/tracks, related artists (Spotify), fan/follower counts where available
- [ ] Merge rules: dedupe by normalized title+date; genre consensus ranking; editable merged genres stored for context
- [ ] Graceful "no data" per source
- [ ] Unit tests with recorded/mocked HTTP fixtures

## Acceptance criteria

- [ ] Confirmed IDs persist and subsequent syncs use IDs not fuzzy name search
- [ ] Spotify discography + top tracks + related artists land in DB
- [ ] SoundCloud tracks/playlists + Deezer releases/fans land when available
- [ ] Duplicate releases across sources collapse to one merged record with source badges
- [ ] Zero references to MusicBrainz or Last.fm in code or config
- [ ] Mocked tests cover success, empty, and error paths

## Implementation notes

- Do not block whole sync if one music source fails; record per-source error.
- Normalize titles (casefold, strip featuring noise) carefully; document algorithm in README later (AA-015).

## Test plan

- Fixture artist → sync → assert merged catalog counts and genre list.
- Missing SoundCloud data → UI-ready "no data" flag in DB/API.

## Out of scope

Library UI (AA-012), context markdown (AA-009).
