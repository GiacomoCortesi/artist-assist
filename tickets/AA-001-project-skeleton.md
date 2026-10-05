---
id: AA-001
title: Project skeleton & packaging
status: proposed
priority: P0
type: story
estimate: L
depends_on: []
blocks: [AA-002, AA-003]
refs:
  - PROMPT.md#tech-stack
  - PROMPT.md#deployment
  - PROMPT.md#configuration-and-security
out_of_scope:
  - Prometheus container or /metrics
  - Publishing scheduler jobs
  - Real OAuth flows
  - Full page implementations beyond shells
---

# AA-001 — Project skeleton & packaging

## Goal

Stand up a runnable ArtistAssist monorepo: FastAPI backend, React+Vite+TypeScript frontend, Docker Compose (`artistassist`), Makefile, env template, and minimal Home/Settings route shells.

## Context

Foundation for every later ticket. Name **ArtistAssist** / Compose project `artistassist` must be consistent from day one.

## Deliverables

- [ ] `backend/` FastAPI app with health endpoint (`GET /api/health`)
- [ ] `frontend/` Vite + React + TS + Tailwind v4 scaffold
- [ ] `docker-compose.yml` services: `caddy`, `backend` (frontend served via Caddy or built into static assets — document choice)
- [ ] Root `Makefile`: `build`, `up`, `down`, `test`, `lint` (stubs OK if empty)
- [ ] `.env.example` with placeholders for OpenAI, platform app IDs/secrets, token encryption key, optional R2
- [ ] Minimal routing: `/` (Home shell), `/settings` (Settings shell), page titles include ArtistAssist
- [ ] Root `README.md` stub: how to copy `.env`, `make up`, open the app
- [ ] `.gitignore` covering `.env`, `node_modules`, `__pycache__`, SQLite files, build artifacts

## Acceptance criteria

- [ ] `make up` (or documented equivalent) brings stack up; health check returns 200
- [ ] Frontend loads and shows ArtistAssist name + tagline placeholder on Home
- [ ] No Prometheus / Grafana / metrics service in Compose
- [ ] Secrets only referenced via env; no secrets committed
- [ ] Compose project name is `artistassist`

## Implementation notes

- Prefer single-user MVP simplicity: one backend process; sync scheduler comes later (AA-008).
- Caddy reverse-proxies API + SPA; Tailscale documented as host concern (detail in AA-015).

## Test plan

- Cold clone → copy `.env.example` → `make up` → hit health + Home in browser.

## Out of scope

Brand tokens/logo (AA-002), SQLite schema (AA-003), platform clients, agent.
