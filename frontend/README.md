# ArtistAssist frontend

React + Vite + TypeScript SPA for ArtistAssist. Production assets are built to `dist/` and served by Caddy; the browser talks to the API same-origin via `/api`.

## Quick Start

From the repo root (preferred; builds SPA then starts Compose):

```bash
make install
make up
```

Local Vite dev server (API via proxy when backend is running separately):

```bash
npm install
npm run dev
```

Other scripts: `npm run build`, `npm run lint`, `npm run preview`.

## Configuration

Build-time variables (from root [`.env.example`](../.env.example) / Vite env):

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `VITE_APP_NAME` | App name for the frontend build | `ArtistAssist` | optional |

Runtime API base path is same-origin `/api` when served behind Caddy. No platform secrets belong in the frontend.
