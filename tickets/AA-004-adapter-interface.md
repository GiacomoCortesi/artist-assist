---
id: AA-004
title: Read-only platform adapter interface
status: proposed
priority: P0
type: story
estimate: M
depends_on: [AA-003]
blocks: [AA-005, AA-006, AA-007]
refs:
  - PROMPT.md#platform-api-clients
out_of_scope:
  - Concrete platform HTTP clients (later tickets)
  - Publish / schedule / hand-off capability implementations
  - Scraping
---

# AA-004 — Read-only platform adapter interface

## Goal

Define a common Python adapter interface and shared Pydantic models so music and social clients plug into sync the same way. All publish-related capabilities fixed to unsupported for MVP.

## Context

"No MCP servers. Build our own Python API clients… behind a common adapter interface."

## Deliverables

- [ ] Shared models: account/profile, post, media, comment, release, track, artist profile, sync cursor/page
- [ ] Capability declaration type (read flags only; publish flags always false)
- [ ] Abstract adapter base: auth/refresh hooks, fetch profile, fetch posts/catalog, rate-limit/retry policy hooks
- [ ] Error types that never swallow failures as success; logging helpers that redact tokens
- [ ] Fake/in-memory adapter for tests
- [ ] Short `docs/adapters.md` describing how to add a client

## Acceptance criteria

- [ ] New client can be registered by implementing the interface without changing sync core contracts
- [ ] Capability object cannot advertise publish in MVP (tests assert false / omitted)
- [ ] Retry/backoff policy documented and unit-tested on the fake adapter
- [ ] Official-APIs-only rule stated in docs; no scrape helpers

## Implementation notes

- Keep interface lean: prefer composition over a giant god-adapter.
- User-Agent strings for outbound HTTP should include `ArtistAssist/<version>`.

## Test plan

- Fake adapter returns typed models; sync-shaped consumer iterates pages.
- Force rate-limit error → retries then raises.

## Out of scope

Spotify/IG/etc. implementations.
