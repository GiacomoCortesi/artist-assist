---
id: AA-008
title: Sync orchestration + topic/sentiment tagging
status: proposed
priority: P0
type: story
estimate: L
depends_on: [AA-005, AA-006, AA-007]
blocks: [AA-009, AA-011]
refs:
  - PROMPT.md#data-sync
out_of_scope:
  - Updating Prometheus gauges
  - Scheduled publishing
  - Statistics recomputation for dashboards
---

# AA-008 — Sync orchestration + topic/sentiment tagging

## Goal

Wire daily (and manual) sync across all adapters: persist data, LLM-tag new posts/comments, merge music, trigger context regen hook, expose sync status APIs.

## Context

After each sync: merge music, regenerate artist context (hook for AA-009), refresh connection/sync status. No metrics pipeline.

## Deliverables

- [ ] In-process scheduler (e.g. APScheduler) with job state in SQLite — **sync only**
- [ ] Manual `POST /api/sync/refresh` (all or per-source)
- [ ] Pipeline steps: fetch → upsert → tag untagged posts (topic taxonomy) → tag untagged comments (sentiment + theme) → music merge → enqueue context regen
- [ ] Bootstrap topic taxonomy (10–15 topics) once from content via LLM; store editable list
- [ ] Per-platform last success / last error / token expiry API for Home/Settings
- [ ] Sonner-friendly sync result payloads (ok / partial / fail)
- [ ] Tests with fake adapters + mocked LLM

## Acceptance criteria

- [ ] Daily schedule configurable; manual refresh works
- [ ] Only untagged items are sent to the LLM
- [ ] One failing platform does not abort others (partial success)
- [ ] No `/metrics` updates; no publish jobs created
- [ ] Sync history queryable for debugging

## Implementation notes

- Context regeneration can be a no-op callback until AA-009 lands; keep interface ready.
- Cap LLM batch sizes; record `openai` purpose tags in logs sparingly (no secrets).

## Test plan

- Run sync with 2 fake platforms (one failing) → partial status + data for the healthy one.
- Second sync does not re-tag already tagged rows.

## Out of scope

Context document contents (AA-009), UI polish (AA-011).
