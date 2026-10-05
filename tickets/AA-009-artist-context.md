---
id: AA-009
title: Artist context markdown generation
status: proposed
priority: P0
type: story
estimate: M
depends_on: [AA-008]
blocks: [AA-010, AA-012, AA-013]
refs:
  - PROMPT.md#artist-context-llm-ready-markdown
out_of_scope:
  - Statistics dashboard panels
  - Overwriting manual events
  - Publishing claims in generated text
---

# AA-009 — Artist context markdown generation

## Goal

Generate structured LLM-ready markdown from SQLite after sync: `artist_profile.md`, `platform_<name>.md`, `events.md`, with YAML front matter, section locks, and regenerate APIs.

## Context

Agent grounding depends on compact, consistent context. Performance insights stay qualitative inside markdown — not a stats UI.

## Deliverables

- [ ] Generators for `artist_profile.md` (sections per prompt; target ~≤2000 tokens for core)
- [ ] Per-platform summaries (last 30 posts + available KPIs as text)
- [ ] `events.md` from Events table (manual source of truth)
- [ ] YAML front matter: type, generated_at, sources, period
- [ ] Per-section manual edit + lock; regen keeps locked sections unless overwrite flag
- [ ] API: get documents, patch section, regenerate one/all (`keep_manual` vs `overwrite`)
- [ ] Hook from sync pipeline
- [ ] Unit tests with fixture DB → golden markdown snippets

## Acceptance criteria

- [ ] Documents regenerate deterministically enough for tests (timestamp aside)
- [ ] Locked sections survive regen
- [ ] Events section never invents events; only reads Events data
- [ ] Music sections cite Spotify / SoundCloud / Deezer only
- [ ] No dashboard/PromQL coupling

## Implementation notes

- Use LLM optionally for tone-of-voice / audience synthesis; keep factual lists template-driven for reliability and stable grounding.
- Store raw markdown in SQLite (and optionally on disk under `data/context/`).

## Test plan

- Fixture posts + releases → generate → assert headings and front matter.
- Lock "Personal information" → change underlying data → regen → locked text unchanged.

## Out of scope

Context UI (AA-012), agent (AA-013).
