---
id: AA-015
title: Hardening, fixtures, README, deployment
status: proposed
priority: P1
type: chore
estimate: M
depends_on: [AA-011, AA-012, AA-013, AA-014]
blocks: []
refs:
  - PROMPT.md#deployment
  - PROMPT.md#configuration-and-security
  - PROMPT.md#implementation-priorities
out_of_scope:
  - Adding Prometheus
  - Adding publish features "while we're here"
  - Multi-user auth
---

# AA-015 — Hardening, fixtures, README, deployment

## Goal

Make the MVP operable for a single musician on Tailscale: docs, mocked API fixtures completeness, token refresh UX polish, empty/error audit, Makefile targets green.

## Context

Last mile so an AI agent or human can run and maintain the app without tribal knowledge.

## Deliverables

- [ ] README: env vars, OAuth app setup per platform, music identity confirm, first sync, Content Studio walkthrough (draft copy + smart media adapt + export), Tailscale + Caddy notes
- [ ] `.env.example` complete and accurate
- [ ] Fixture pack for all adapters used in CI tests
- [ ] Token expiry / reconnect UX audited on Home + Settings
- [ ] Empty/loading/error pass on all six pages
- [ ] `make test`, `make lint`, `make build` succeed in CI-like local run
- [ ] Confirm global out-of-scope still absent (grep: prometheus, musicbrainz, last.fm, publish schedule)
- [ ] Optional: short `docs/runbook.md` for sync failures

## Acceptance criteria

- [ ] New machine can follow README to a working Home + successful mock or real sync path
- [ ] CI/local test suite does not need live platform credentials
- [ ] No secrets in repo
- [ ] Grep audit for out-of-scope features passes (document allowed mention sites, e.g. PROMPT out-of-scope table)
- [ ] User-Agent / Compose name / UI name all say ArtistAssist / `artistassist`

## Implementation notes

- Prefer fixing sharp edges discovered while writing the walkthrough.
- Keep R2 optional; document local disk export as default.

## Test plan

- Follow README from clean checkout on a second shell profile.
- Run full test suite offline.

## Out of scope

New product features beyond polish of accepted MVP tickets.
