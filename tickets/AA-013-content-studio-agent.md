---
id: AA-013
title: Content Studio agent + smart media pipeline
status: proposed
priority: P0
type: story
estimate: L
depends_on: [AA-009, AA-010]
blocks: [AA-014]
refs:
  - PROMPT.md#content-agent--media-aa-013--aa-014
  - AGENTS.md
out_of_scope:
  - Publishing or scheduling posts to platforms
  - Claiming posts were published via ArtistAssist
  - Prometheus agent metrics
  - Gutting media/agent quality for "API cost savings"
---

# AA-013 — Content Studio agent + smart media pipeline

## Goal

Build the OpenAI Agents SDK backend that helps **design and prepare content in general** (not campaigns only), grounded on all user custom information, plus a media library with **smart autocrop / format adaptations** for social platforms — export-ready, never publish.

## Context

MVP focus #2. The agent is a general content co-designer that uses artist context, synced history, music, events, and media. Campaigns are one mode, not the only mode.

## Deliverables

- [ ] Agent configured with chat + image models from `.env`
- [ ] Tools to read context docs, events, releases, recent posts/comments themes, media library
- [ ] Tools to create/update content drafts and optional multi-post plans (when the user wants a series/campaign)
- [ ] Media library: upload/import originals; store metadata; reference synced post media where available
- [ ] Smart adaptation pipeline: from one master image produce platform variants with smart autocrop / focal-point / face-aware crop when possible, else high-quality center/safe crop; Pillow for deterministic resize and safe-area padding
- [ ] Format presets at least: feed 4:5, square 1:1, story/reel 9:16, landscape 16:9; map presets to platforms (IG, FB, Threads, TikTok, YouTube) in docs/code
- [ ] Manual focal-point / crop override API; regenerate variants from the same original
- [ ] Optional OpenAI image generate/edit for new masters when the user asks
- [ ] Streaming chat API for Content Studio
- [ ] Persist drafts, plans, originals, derived variants (local disk default; optional R2)
- [ ] Export package builder: caption + hashtags + selected adapted media (zip or structured payload)
- [ ] Safety rules: no invented dates/links/metrics; no publish claims
- [ ] Tests with mocked OpenAI + fixture images covering crop variants

## Acceptance criteria

- [ ] Agent answers grounded on current context (unique injected phrase appears in draft copy)
- [ ] Can complete non-campaign tasks (e.g. “rewrite this caption for TikTok”, “adapt this photo for IG feed + story”) without forcing a campaign object
- [ ] Multi-post plan supported when requested
- [ ] Uploading one landscape photo yields correct-ratio variants for the required presets without uploading to social APIs
- [ ] Face/subject-aware or focal-point crop demonstrably keeps subject in frame better than naive center-crop on a fixture with off-center subject (test or documented heuristic + unit assert on crop box)
- [ ] Drafts and media variants reloadable
- [ ] API has **no** publish/schedule endpoints
- [ ] Export returns downloadable package metadata including adapted files

## Implementation notes

- Prefer tool-calling over stuffing the entire DB into the system prompt.
- Conversation threads may be scratch sessions or linked to a plan/draft.
- Document crop algorithm and platform preset table in `docs/media-formats.md`.

## Test plan

- Fixture context → “draft an IG caption for my next concert” → draft in DB, no publish.
- Ask to invent a ticket URL → refuse or mark unknown.
- Fixture off-center subject image → adapt to 4:5 and 9:16 → assert output sizes and crop contains expected subject region.
- Export zip contains caption file + variant images.

## Out of scope

Frontend chat/media UX (AA-014).
