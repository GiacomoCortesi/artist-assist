---
id: AA-014
title: Content Studio UI + media adaptations
status: proposed
priority: P0
type: story
estimate: L
depends_on: [AA-002, AA-013]
blocks: [AA-015]
refs:
  - PROMPT.md#content-agent--media-aa-013--aa-014
  - PROMPT.md#brand--ui
out_of_scope:
  - Publish button / schedule button / hand-off upload
  - Platform-faithful UI clones
---

# AA-014 — Content Studio UI + media adaptations

## Goal

Ship Content Studio: chat with the general content agent, drafts/plans, media library, format previews with smart-crop results, crop refinement, and copy/export — for any content task, not only campaigns.

## Context

Primary creative surface. Uses all artist context via the agent. Preparation previews only.

## Deliverables

- [ ] Chat panel with streaming text (Motion-friendly; respect reduced motion)
- [ ] Side panel: current draft(s); optional multi-post plan as timeline/checklist when present
- [ ] Selected draft: caption, hashtags, linked event/release if any
- [ ] Media library browser + upload; attach media to draft
- [ ] Neutral device-style preview frames for presets (4:5, 1:1, 9:16, 16:9) showing adapted crops
- [ ] Crop controls: set focal point / adjust crop; regenerate platform variants
- [ ] Actions: save draft, regenerate/adapt creative, copy caption/hashtags, download export package
- [ ] Explicit absence of Publish / Schedule controls
- [ ] Empty state for first content request (examples: caption, adapt photo, plan a series)
- [ ] Toasts for save/export/errors

## Acceptance criteria

- [ ] User can chat → save draft → adapt media → export without leaving Studio
- [ ] Campaign/series plan is optional UI, not required to start
- [ ] Previews update when caption or adapted media changes
- [ ] Works on mobile (sheet/drawer patterns OK)
- [ ] No control that calls social publish APIs
- [ ] Accessibility: focus order in chat + editor + crop controls sane

## Implementation notes

- Keep previews neutral (not IG/TikTok skins).
- Wire Home counters to open drafts / export-ready items once this lands.

## Test plan

- Manual: upload photo, ask agent to adapt for IG feed + TikTok, refine focal point, export zip.
- Manual: request a single caption with no media.
- Smoke: deep-link from Home to open drafts.

## Out of scope

Hardening/docs (AA-015).
