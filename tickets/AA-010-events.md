---
id: AA-010
title: Events CRUD + post-derived suggestions
status: proposed
priority: P0
type: story
estimate: M
depends_on: [AA-003, AA-009]
blocks: [AA-012, AA-013]
refs:
  - PROMPT.md#artist-context-llm-ready-markdown
  - PROMPT.md#4-events
out_of_scope:
  - LLM overwriting confirmed events
  - Auto-publishing event promos
---

# AA-010 — Events CRUD + post-derived suggestions

## Goal

Ship Events domain: manual CRUD UI+API, feed `events.md`, and accept/dismiss LLM suggestions detected from posts during context generation.

## Context

Events are never generated as truth by the LLM — only suggested. Confirmed events feed context and the content agent.

## Deliverables

- [ ] Event model fields: datetime, title, type (`concert|release|masterclass|other`), venue, city, ticket/info link, notes
- [ ] REST CRUD + list upcoming from today
- [ ] Suggestion records linked to source post(s); accept → create event; dismiss → hide
- [ ] Events page UI (mobile-first) using design system
- [ ] Context regen consumes confirmed events only
- [ ] Tests for CRUD + accept/dismiss

## Acceptance criteria

- [ ] Creating/editing/deleting events reflected in `events.md` on next regen
- [ ] Suggestions cannot mutate Events until accepted
- [ ] Empty state designed (icon + sentence + CTA to add event)
- [ ] No publish/schedule actions on the page

## Implementation notes

- Suggestion detection can run as part of context generation (AA-009) and write into suggestions table.

## Test plan

- Create event → regen → appears in `events.md`.
- Suggestion accept creates event and clears suggestion.

## Out of scope

Campaign linking UI details (AA-014 can attach drafts to events via existing IDs).
