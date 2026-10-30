# Talent Matcher: frontend (Next.js 16)

The web portal for the RAG Talent Matcher. Pages render on the Next.js server and call FastAPI
server-to-server; the browser only ever talks to this server.

## Run it (development)
```powershell
cd frontend
npm install            # once, and after package.json changes
npm run dev            # http://localhost:3000  (the backend must run on port 8010)
```
Log in with a portal user (created with `python -m scripts.create_user` in `backend/`).

## Commands
| Command | What it does |
|---|---|
| `npm run dev` | Development server with instant reload |
| `npm run build` then `npm run start` | Production build and server |
| `npm run check` | Types, lint, formatting and unit tests in one go |
| `npm run typecheck` | Generate route types, then check all TypeScript |
| `npm run lint` | ESLint (Next.js + React Compiler rules) |
| `npm run format` / `format:check` | Prettier (also sorts Tailwind classes) |
| `npm run test` | Unit tests (Vitest + Testing Library) |
| `npm run test:e2e` | Browser tests (Playwright); see `playwright.config.ts` for setup |
| `npm run api:types` | Regenerate `src/lib/api/schema.d.ts` from the running backend's `/openapi.json` |

## Configuration (`.env.local`, optional)
| Variable | Default | Meaning |
|---|---|---|
| `BACKEND_URL` | `http://127.0.0.1:8010` | Where FastAPI runs (server-side only) |
| `HTTPS` | `false` | `true` when served over HTTPS: Secure cookie, HSTS |

Settings are validated at startup (`src/lib/env/schema.ts`). `BACKEND_URL` is also compiled into the
`/api` rewrite at build time, so rebuild after changing it.

## Where things are
```
src/
  proxy.ts                    optimistic login check before every page
  app/                        ROUTES ONLY: thin files that compose features
    (auth)/login/             sign-in page (static; works without JavaScript)
    (portal)/                 signed-in pages; layout = shell + streamed user parts
    auth/session-expired/     Route Handler: clears an invalid cookie, back to /login
  features/                   one folder per business area
    auth/                     Server Actions (login/logout), zod schemas, login form, account menu
    dashboard/                queries (server-only data access) + its cards
  components/
    ui/                       design system (shadcn/ui conventions on Radix primitives)
    layout/                   app shell, navigation, page header
  lib/
    api/                      typed FastAPI client (generated types), error messages
    auth/                     session (server-only), cookie constants, JWT expiry, safe redirects
    env/                      validated settings
e2e/                          Playwright browser tests
```
See `docs/15 - Step 11 Explained - The Next.js Frontend.md` for the full explanation.
