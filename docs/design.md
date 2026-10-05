# ArtistAssist design system

## Brand

- **Name:** ArtistAssist
- **Tagline:** Your social media assistant
- **Logo:** AA monogram (SVG, `currentColor`). Accent variant uses vermilion.
- **Assets:** `frontend/public/brand/` — mark, full lockup, favicon, PWA icon, manifest.

### Logo rules

- Prefer mark at small sizes (≥16px). Full lockup when space allows.
- Never recolor the accent mark to purple or other brand-off hues.
- Maintain clear space ≈ 0.25× mark height around the logo.

## Color

Minimal B/W with vermilion accent ≈ `#FF4D2E` as OKLCH `oklch(0.62 0.22 29)` (light) /
`oklch(0.65 0.22 29)` (dark). CSS variables + Tailwind `@theme` in `src/index.css`.

### Contrast (WCAG AA)

| Pair | Theme | Notes |
| --- | --- | --- |
| foreground / background | both | Near black/white — AAA for body text |
| primary-foreground / primary | both | White on vermilion — AA for UI labels |

## Typography

Geist Sans + Geist Mono via Fontsource (self-hosted). Scale: body `text-sm`/`text-base`,
page titles `text-2xl`–`text-4xl` semibold tracking-tight.

## Spacing & radius

8px rhythm; radii `--radius-sm/md/lg` (0.25–0.5rem). Prefer flat surfaces over card stacks.

## Motion

Use Motion for intentional entrance (opacity/y). Respect `prefers-reduced-motion` (global CSS
short-circuits animations).

## Theme

System / Light / Dark. Default follows `prefers-color-scheme`. Persisted in `localStorage`
key `artistassist-theme`. Inline boot script prevents FOUC.

## Chrome

Desktop sidebar + mobile bottom tabs: Home, Context, Studio, Settings.
