# ArtistAssist MVP — Dev sprint backlog

**Agent brief (autonomous run):** [`../PROMPT.md`](../PROMPT.md) — implements all tickets, tests offline, Fable build-efficiency rules, out-of-scope.

**Format:** one Markdown file per ticket + YAML front matter (see [`_SCHEMA.md`](_SCHEMA.md)).  
Agents: execute in dependency order (or parallel phases in `PROMPT.md`), mark criteria `[x]`, set `status: done`, append `PROGRESS.md`.

## Sprint order (dependency-respecting)

| Order | ID | Title | Size | Depends on |
| ---: | --- | --- | --- | --- |
| 1 | [AA-001](AA-001-project-skeleton.md) | Project skeleton & packaging | L | — |
| 2 | [AA-002](AA-002-brand-design-system.md) | Brand, design system & styleguide | M | AA-001 |
| 3 | [AA-003](AA-003-data-layer.md) | SQLite data layer & encrypted tokens | L | AA-001 |
| 4 | [AA-004](AA-004-adapter-interface.md) | Read-only platform adapter interface | M | AA-003 |
| 5 | [AA-005](AA-005-music-clients.md) | Music clients: Spotify, SoundCloud, Deezer + merge | L | AA-004 |
| 6 | [AA-006](AA-006-social-clients-meta.md) | Social clients: Instagram, Facebook, Threads | L | AA-004 |
| 7 | [AA-007](AA-007-social-clients-tiktok-youtube.md) | Social clients: TikTok, YouTube | M | AA-004 |
| 8 | [AA-008](AA-008-sync-orchestration.md) | Sync orchestration + topic/sentiment tagging | L | AA-005, AA-006, AA-007 |
| 9 | [AA-009](AA-009-artist-context.md) | Artist context markdown generation | M | AA-008 |
| 10 | [AA-010](AA-010-events.md) | Events CRUD + post-derived suggestions | M | AA-003, AA-009 |
| 11 | [AA-011](AA-011-settings-home.md) | Settings + Home pages | M | AA-002, AA-008 |
| 12 | [AA-012](AA-012-library-context-ui.md) | Artist library + Context UI | L | AA-002, AA-009, AA-010 |
| 13 | [AA-013](AA-013-content-studio-agent.md) | Content agent + smart media pipeline | L | AA-009, AA-010 |
| 14 | [AA-014](AA-014-content-studio-ui.md) | Content Studio UI + media adaptations | L | AA-002, AA-013 |
| 15 | [AA-015](AA-015-hardening-docs.md) | Hardening, fixtures, README, deployment | M | AA-011–AA-014 |

## Global out of scope (all tickets)

- Publishing / scheduling / hand-off upload to platforms
- Statistics dashboard, Recharts analytics panels, Prometheus / `/metrics`
- MusicBrainz, Last.fm
- Multi-user auth (Tailscale is the access control)
