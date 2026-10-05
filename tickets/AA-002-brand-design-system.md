---
id: AA-002
title: Brand, design system & styleguide
status: proposed
priority: P0
type: story
estimate: M
depends_on: [AA-001]
blocks: [AA-011, AA-012, AA-014]
refs:
  - PROMPT.md#brand-design-and-styling
out_of_scope:
  - Statistics chart palettes / Recharts
  - Publishing queue device frames beyond shared preview primitives (preview frames land in AA-014)
---

# AA-002 — Brand, design system & styleguide

## Goal

Ship ArtistAssist visual identity: AA monogram logo pack, vermilion accent tokens in OKLCH, Geist fonts, theme switcher, layout chrome (sidebar + mobile tab bar), and a `/styleguide` route.

## Context

All product pages must share one look. Mobile-first; black/white + `#FF4D2E`-class accent.

## Deliverables

- [ ] Logo assets in `frontend/public/brand/` (full, mark, favicons, PWA icons, web manifest)
- [ ] CSS variables / Tailwind v4 `@theme` + shadcn tokens (light/dark)
- [ ] System / Light / Dark switch persisted in `localStorage`; no flash on load
- [ ] Geist Sans + Geist Mono via Fontsource (self-hosted)
- [ ] App shell: desktop sidebar + mobile bottom tabs (Home, Library, Context, Events, Studio, Settings)
- [ ] Shared empty / loading / error state components
- [ ] `docs/design.md` (logo rules, colors, type scale, spacing, motion, reduced-motion)
- [ ] Dev-only `/styleguide` route

## Acceptance criteria

- [ ] Logo legible at 16px; uses `currentColor`; accent variant exists
- [ ] WCAG AA contrast check documented for primary text/actions in both themes
- [ ] Theme follows `prefers-color-scheme` by default and can be overridden
- [ ] Motion utilities respect `prefers-reduced-motion`
- [ ] Styleguide renders tokens + core components in both themes
- [ ] No purple-gradient / generic AI aesthetic defaults; vermilion accent only for primary UI signals

## Implementation notes

- Install shadcn/ui primitives listed in prompt as needed (Card, Tabs, Dialog, Sheet, etc.); Command palette can be stubbed until pages exist.
- Grain / radial accent behind Home header can be a shared CSS utility.

## Test plan

- Toggle System/Light/Dark; hard-refresh; no FOUC.
- Resize to mobile width: bottom tabs usable.
- Open `/styleguide` and spot-check tokens.

## Out of scope

Full page content, charts, publishing UI.
