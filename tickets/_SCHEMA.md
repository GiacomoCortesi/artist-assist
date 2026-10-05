# Ticket schema (for humans and AI agents)

Each ticket is a Markdown file with YAML front matter.

## Front matter fields

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Stable ID, e.g. `AA-001` |
| `title` | string | Short imperative title |
| `status` | enum | `proposed` \| `accepted` \| `rejected` \| `in_progress` \| `done` \| `blocked` |
| `priority` | enum | `P0` \| `P1` \| `P2` |
| `type` | enum | `epic` \| `story` \| `chore` \| `spike` |
| `estimate` | string | Rough size: `S` / `M` / `L` / `XL` |
| `depends_on` | string[] | Ticket IDs that must be `done` first |
| `blocks` | string[] | Ticket IDs waiting on this one |
| `refs` | string[] | Paths into `PROMPT.md` or other docs |
| `out_of_scope` | string[] | Explicit non-goals for this ticket |

## Body sections (required)

1. **Goal** — one paragraph
2. **Context** — why / links to prompt
3. **Deliverables** — concrete artifacts
4. **Acceptance criteria** — checkbox list (definition of done)
5. **Implementation notes** — hints for agents (optional)
6. **Test plan** — how to verify
7. **Out of scope** — repeat/expand front matter

## Agent rules

- Follow `PROMPT.md` for autonomy, Fable build-efficiency, and global out-of-scope.
- Respect `depends_on`: all listed tickets must be `done` (or completed earlier in the same autonomous run before starting dependents).
- Never implement items listed under `out_of_scope` or in `PROMPT.md` out-of-scope.
- Prefer fixtures/mocks; do not spend OpenAI/platform quota to develop or CI-test.
- When finishing: mark acceptance criteria with `[x]`, set `status: done`, leave a short "Done notes" section, update `PROGRESS.md`.
