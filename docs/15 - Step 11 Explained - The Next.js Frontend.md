# 15 · Step 11 Explained: The Next.js Frontend

This document explains the web portal's foundation: **why** it exists, the **web and Next.js 16 fundamentals** behind it, the **architecture** (where data is loaded, how login works across two servers, how errors and security are handled), **every file**, the **developer and end-user flows**, how it is **tested**, and the **alternatives** up to enterprise level.

It describes the **second version (Step 11b)**. The first version worked but did not follow how Next.js 16 is meant to be used; section 2 explains what changed and why, so you can learn from the comparison.

**Read first:** 13 (Step 9, login) and 14 (Step 10, agent). **Next:** Step 12 (admin portal pages) and Step 13 (agent chat page) are built on this foundation.

---

## 1. Why Step 11 exists

Steps 1–10 built a complete backend, but it can only be used through `/docs` (Swagger) or Python scripts. Resource managers and admins need a **portal**: sign in, see the state of the system, upload resumes, run matches, chat with the agent.

Step 11 builds the **foundation** every later page stands on:

| Foundation piece | Why every page needs it | Where |
|---|---|---|
| Next.js 16 + TypeScript + Tailwind 4 | The framework, the language, the styling | `package.json`, `next.config.ts` |
| A typed, server-only way to call FastAPI | One place for the token, errors, "session ended" | `src/lib/api/` |
| API types generated from FastAPI | Frontend and backend can't silently drift apart | `src/lib/api/schema.d.ts` |
| Sign in / sign out as Server Actions | Secure cookie set by the server; works without JavaScript | `src/features/auth/` |
| The session on the server | Who is signed in, their role, read once per request | `src/lib/auth/session.ts` |
| Route protection | No portal page renders for someone who isn't signed in | `src/proxy.ts` |
| The app shell | One consistent frame with role-aware navigation | `src/components/layout/` |
| A design system | Consistent, accessible building blocks; one place to re-theme | `src/components/ui/`, `globals.css` |
| Validated settings and security headers | Clear startup errors; protection against XSS and clickjacking | `src/lib/env/`, `next.config.ts` |
| Tests | Logic, components and real browser flows checked automatically | `*.test.ts(x)`, `e2e/` |
| A first real page: the dashboard | Proves the whole chain works end to end | `src/features/dashboard/` |

> **Step 11 creates the portal's skeleton: a Next.js 16 app whose pages render on the server, call FastAPI with the signed-in person's token, stream each section in as its data arrives, and keep the login token where page JavaScript can never read it.**

There's no new AI in this step, but the dashboard shows the AI side's health (Ollama, the three models) and the knowledge base (resumes in each pipeline stage).

---

## 2. Version 1 vs version 2: what changed and why

The first version was a working **single-page app inside Next.js**: every page was a Client Component that loaded its data in the browser with `useEffect` after the page appeared. When asked "is this world-class?", the honest answer was no. It ignored Next.js's core model and had several hand-made pieces that industry projects don't hand-make.

| Topic | Version 1 | Version 2 (now) | Why it's better |
|---|---|---|---|
| Where data loads | In the browser, after the page appears (`useEffect`) | On the Next.js server, while rendering, streamed in behind `<Suspense>` | No empty-page-then-spinners; less JavaScript; the token never has to be usable by the browser |
| Session | `SessionProvider` asked `/api/auth/me` from the browser | `getCurrentUser()` on the server with `"use cache: private"` | The pattern in the Next.js 16 "Authentication with Cache Components" guide |
| Login | Browser `fetch` to `/api/auth/login`; FastAPI set the cookie | A **Server Action** calls FastAPI server-to-server and sets the cookie | Works without JavaScript, built-in CSRF check, input validated with zod on the server |
| API types | Written by hand in `types.ts` | **Generated** from FastAPI's `/openapi.json` | A backend change becomes a compile error, not a runtime surprise |
| API calls | `api()` wrapper using `fetch` | `openapi-fetch` client: paths, parameters and responses all typed | Typos in URLs or fields are caught by the editor |
| Errors | Thrown, shown as text | **Expected** errors returned as values (`ApiResult`); **unexpected** ones caught by per-section boundaries (`catchError`) | One broken card can't take the page down; production never leaks error details |
| Components | 7 components in one file | shadcn/ui conventions on **Radix** primitives, `cva` variants, `lucide` icons | Keyboard and screen-reader behaviour done right (menus, labels); easy to extend |
| Dashboard counts | Downloaded up to 500 employees to count them | New `GET /api/overview` returns counts only | The same speed with 50 or 50,000 employees |
| Settings | `process.env.BACKEND_URL` read raw | Validated with zod at startup | A typo stops startup with the variable's name |
| Security headers | None | CSP, nosniff, frame-ancestors, Referrer-Policy, Permissions-Policy (HSTS on HTTPS) | Defence against XSS, clickjacking, data leaks |
| Structure | By file type (`components/`, `lib/`) | By **feature** (`features/auth`, `features/dashboard`) on top of shared `components/` and `lib/` | Scales to Steps 12–13 without a junk drawer |
| Quality gates | Lint + typecheck | + Prettier, 43 unit tests (Vitest), 10 browser tests (Playwright), `npm run check` | Regressions caught before you see them |
| Compiler | Default | **React Compiler** on (automatic memoisation), **typed routes** on | Faster re-renders without `useMemo`; broken links don't compile |
| Error page API | `reset()` (older Next.js) | `retry()` (Next.js 16) | `retry` re-fetches on the server, so it can recover from a server error |

---

## 3. Web and Next.js 16 fundamentals

### 3.1 What runs where
```
 Browser (Edge/Chrome)            Next.js server (Node.js, :3000)                   FastAPI (Python, :8010)
 ─────────────────────            ────────────────────────────────                  ───────────────────────
 HTML + CSS + a little JS         proxy.ts: optimistic login check
 cookie rtm_access (HttpOnly) ──▶ renders pages (Server Components) ──Bearer token──▶ the API from Steps 2-10
                              ◀── streams HTML as each part is ready ◀──── JSON ──── database, Ollama, ChromaDB
 form POST (Server Action)    ──▶ login/logout actions: validate, call FastAPI, set/delete the cookie
 (Step 12) fetch /api/...    ──▶ rewrite: forwards unchanged, with the cookie ──────▶ (resume uploads)
 (Step 13) fetch /bff/...    ──▶ Route Handler relay: cookie → Bearer, unbuffered ──▶ (agent stream, SSE)
```

### 3.2 React in one minute
A **component** is a function that returns UI (written in JSX, HTML-like syntax inside TypeScript):
```tsx
function StatTile({ label, value }: { label: string; value: number }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}
<StatTile label="Employees" value={16} />
```
**Props** are inputs; **state** (`useState`) is data that changes and re-draws the component; **hooks** are functions starting with `use…` that give components abilities (state, the current URL, a form's pending status).

### 3.3 Server Components and Client Components
| | Server Component (the default) | Client Component (`"use client"` at the top) |
|---|---|---|
| Runs | Only on the server | On the server for the first HTML, then in the browser |
| Can | `await` data, read cookies, use secrets | Use state, effects, clicks, the current URL |
| Ships JavaScript | None | Its code is sent to the browser |
| In this project | Pages, layouts, the dashboard cards, the session parts | The login form, nav links (active page), account menu, error boundaries, auto-refresh |

Rule of thumb: **server by default; client only for the interactive leaf**. Data passed from server to client must be plain data (strings, numbers, objects), which is why the navigation passes an icon *name* (`"dashboard"`) and the client maps it to the icon component.

### 3.4 Cache Components, the static shell and streaming
With `cacheComponents: true` (the Next.js 16 model), every page is split in two at build time:
- the **static shell**: everything that doesn't need the request (layout, headings, skeletons). It is prerendered once and served instantly;
- the **dynamic parts**: anything that reads cookies, the URL's `?search`, or uncached data. They **must** sit inside `<Suspense fallback={...}>`, and stream into the page when ready.

```
Time ──▶
0 ms     shell arrives: sidebar, "Dashboard", 4 grey skeletons            (instant)
~30 ms   account menu + role-based links stream in                        (/api/auth/me)
~40 ms   number tiles stream in                                          (/api/overview + /api/resumes/stats)
~50 ms   projects card streams in                                        (/api/projects)
~300 ms  system health streams in                                        (/api/health asks Ollama)
```
The build output marks such routes **◐ Partial Prerender**. Reading `cookies()` outside a Suspense boundary is a **build error**: Next.js enforces this structure rather than letting a page silently become slow.

### 3.5 `"use cache: private"`
Next.js 16 has three caching directives. We use one, for one function:

| Directive | Stored | Can read cookies? | Used here? |
|---|---|---|---|
| `"use cache"` | Server memory, shared by everyone | No | No: all our data is per-user or live |
| `"use cache: remote"` | A shared remote cache | No | No |
| `"use cache: private"` | **Browser memory only** (plus reuse within one request) | **Yes** | `getCurrentUser()` |

So the shell's menu, the account corner and the page can all call `getCurrentUser()`, but FastAPI is asked **once per request**, and moving between pages reuses the answer for a few minutes (default `stale` = 5 min). The user's data is never stored in a server cache that other users could hit.

### 3.6 Server Actions
A function in a file marked `"use server"` that can be used as a form's `action`:
```tsx
<form action={formAction}>  ...  </form>     // formAction comes from useActionState(login, {})
```
Submitting POSTs the fields to the Next.js server, which runs `login()`. The page needs no `fetch` code, the form works **before or without JavaScript**, and Next.js rejects the POST if its `Origin` header doesn't match the site (CSRF protection). Every Server Action is a public endpoint, so it validates its input (zod) and the backend checks again.

`useActionState(action, initialState)` (React 19) returns `[state, formAction, pending]`: what the action returned last time (errors), the function for `<form action>`, and whether it's running (to disable the button).

### 3.7 Proxy
`proxy.ts` (called "middleware" before Next.js 16) runs before every page request. The Next.js docs recommend only **optimistic** checks there (read a cookie, redirect); the real authorization happens close to the data.

### 3.8 TypeScript, generated types and typed routes
TypeScript adds **types** to JavaScript. Three levels in this project:
1. **Our own code**: `strict` mode plus `noUncheckedIndexedAccess` (an array lookup may be `undefined`; TypeScript makes you handle it).
2. **The API**: `schema.d.ts` is generated from FastAPI. `result.data.employees.total` autocompletes; `result.data.employes` doesn't compile.
3. **Links**: `typedRoutes: true` makes `<Link href="/emplyees">` a compile error.

### 3.9 Tailwind, design tokens and shadcn/ui
Styles are small classes in the markup (`rounded-xl border bg-card p-4`). Colours are **design tokens** in `globals.css` (`--primary`, `--muted-foreground`, …) in **OKLCH** (equal number steps look like equal brightness steps, which makes contrast easier), with a second set for dark mode. The names follow **shadcn/ui**, the most widely used React component approach in 2025–26. You don't install it as a library; you own the component source, built on **Radix** primitives that implement the accessibility rules (WAI-ARIA patterns) for menus, labels and dialogs.

---

## 4. The architecture

### 4.1 Layers (and the one-way rule)
```
src/app/          ROUTES: thin files; decide layout, Suspense boundaries, metadata. No business logic.
   │ uses
src/features/     BUSINESS AREAS: auth (actions, schemas, forms), dashboard (queries, cards). Steps 12-13 add more.
   │ uses
src/components/   SHARED UI: ui/ (design system), layout/ (shell, nav), boundaries, placeholders
   │ uses
src/lib/          FOUNDATIONS: api/ (typed client, errors), auth/ (session, cookie, redirects, JWT), env/, utils
```
A layer may use the layers **below** it, never above. `lib/` knows nothing about pages; `components/ui/` knows nothing about the dashboard. That's the same idea as the backend's `api → services → db` layers (doc 01).

### 4.2 The Data Access Layer (DAL)
The Next.js data-security guide recommends one server-only place that fetches data, checks access and returns small objects. Ours:

| Part | Role |
|---|---|
| `lib/api/client.ts` → `request()` | Reads the cookie, creates a typed client with `Authorization: Bearer <token>`, runs the call, turns the outcome into an `ApiResult` |
| `lib/auth/session.ts` → `getCurrentUser()` | `GET /api/auth/me`, returns a narrow `SessionUser` (id, email, fullName, role): no token, no timestamps |
| `features/*/queries.ts` | One function per backend read a feature needs (`getOverview`, `getHealth`, …) |

Every file in the DAL starts with `import "server-only"`: if a Client Component ever imports it, **the build fails**, so the token and the backend address can't leak into browser JavaScript.

FastAPI stays the **only** place that decides who may do what (Step 9). Next.js never verifies the JWT (it doesn't have `JWT_SECRET`); it forwards it. This is the "External HTTP APIs, zero trust" approach from the same guide.

### 4.3 Two paths to FastAPI
| Path | Used by | How the token travels |
|---|---|---|
| **Server-to-server** (now) | Pages, layouts, Server Actions | Next.js reads the HttpOnly cookie and sends `Authorization: Bearer …` |
| **Rewrite** `/api/*` → FastAPI | Browser code that sends files straight to FastAPI: resume uploads (Step 12a) | The browser sends the cookie itself; FastAPI accepts the cookie (Step 9) |
| **Relay** `/bff/*` (Route Handlers, Step 13) | Browser code that needs a live stream: the agent chat | Next.js reads the cookie and sends `Authorization: Bearer …`; the stream is passed through with `no-transform` |

**Step 13 finding:** the rewrite was meant for the agent stream too, but Next.js compresses rewritten responses with gzip, and that **buffers** SSE (all events arrived at the end, 4.2 s, instead of every 0.7 s). A Route Handler controls its own headers, so `Cache-Control: no-cache, no-transform` lets every event through at once. Details in doc 17.

The cookie name `rtm_access` therefore must match the backend's `AUTH_COOKIE_NAME`.

### 4.4 Who checks the login, and where
| Layer | Check | Strength |
|---|---|---|
| `proxy.ts` | Cookie present and its `exp` in the future? | **Optimistic**: no signature check. Avoids rendering a portal page for an obvious visitor |
| `request()` (DAL) | FastAPI answered 401 → `/auth/session-expired` | Ends sessions that FastAPI rejects |
| FastAPI `get_current_user` | Signature, expiry, user still active, role | **Authoritative**, on every call |
| `AdminOnly`, `navItemsFor(role)` | Hide admin pages and links | **Convenience only**: the backend answers 403 regardless |

**Why `/auth/session-expired` exists (a subtle loop):** if FastAPI rejects a token that still *looks* valid (deactivated user, changed `JWT_SECRET`, forged token), redirecting to `/login` isn't enough: the proxy still sees a valid-looking cookie and sends `/login` back to `/`, forever. Pages aren't allowed to change cookies, so the API client redirects to a **Route Handler** that deletes the cookie, then goes to `/login?expired=1`.

### 4.5 Errors: expected vs unexpected
| Kind | Example | Handled by | The user sees |
|---|---|---|---|
| Expected | Backend down, 404, 429, validation error | Returned as `{ ok: false, message }` and shown **inside the card** | "Cannot reach the backend. Is FastAPI running…?" |
| Session ended | 401 | `request()` → `/auth/session-expired` | Login page: "Your session has ended" |
| Unexpected (a bug) | A component throws | `SectionBoundary` (Next.js 16 `catchError`) around each card; `error.tsx` per segment; `global-error.tsx` as last resort | "… could not be shown" + **Try again** (`retry()` re-renders that part on the server) |

In production Next.js replaces a thrown error's message with a generic text and a `digest` ID (the real message is in the server log). That's why expected problems are returned as values: their friendly messages survive.

### 4.6 Caching decisions
| Data | Cached? | Why |
|---|---|---|
| Who is signed in | `"use cache: private"` (browser, ~5 min; per request on the server) | Asked by 3 parts of every page; changes rarely |
| Overview, pipeline, projects, health | **Not cached** | Live numbers while resumes are processed; each call is milliseconds of SQL. They stream inside Suspense, so they never delay the frame |
| Live dashboard | `AutoRefresh` calls `router.refresh()` every 10 s **only while resumes are in progress** | Idle portal = zero background requests |

### 4.7 Security, layer by layer
| Threat | Defence | Where |
|---|---|---|
| Token theft by injected script (XSS) | Cookie is **HttpOnly** (page JS can't read it); token only used server-side | `setSessionCookie`, DAL |
| Injected script running at all | **Content-Security-Policy**: scripts, styles, connections only from this site; no plugins | `next.config.ts` |
| Cross-site form posts (CSRF) | `SameSite=Lax` cookie + Server Actions' Origin/Host check | Cookie options, Next.js |
| Clickjacking (portal in a hidden iframe) | `frame-ancestors 'none'` + `X-Frame-Options: DENY` | `next.config.ts` |
| Open redirect via `?next=` | `safeNextPath()`: same-site paths only (rejects `//x`, `/\x`, `https://…`, control characters, `/login`) | `lib/auth/redirect.ts` |
| Secrets in browser bundles | `server-only` imports; no `NEXT_PUBLIC_` variables | DAL, `lib/env` |
| Content sniffing, referrer leaks | `nosniff`, `strict-origin-when-cross-origin` | `next.config.ts` |
| Plain-HTTP cookie leaks in production | `HTTPS=true` → `Secure` cookie, HSTS, `upgrade-insecure-requests` | `.env.local` |

**The CSP trade-off:** the strictest CSP uses a fresh **nonce** per request, but nonces force every page to render per request and are incompatible with the prerendered static shell. Next.js documents a "without nonces" policy for this case, which allows inline scripts (`'unsafe-inline'`, needed for Next.js's own inline hydration data). We chose instant pages + that policy; a bank-grade setup might choose nonces and accept slower pages.

---

## 5. The flows

### 5.1 Developer flow
```powershell
cd frontend
npm install                    # once, and after package.json changes
npm run dev                    # http://localhost:3000, instant reload; backend on :8010
npm run check                  # before committing: types + lint + formatting + unit tests
npm run format                 # fix formatting (and sort Tailwind classes)
npm run api:types              # after changing a backend API (backend running) ...
npm run typecheck              # ... then see every place in the frontend that must follow
npm run build; npm run start   # production build and server
npm run test:e2e               # browser tests (first time: npx playwright install chromium;
                               #   set $env:E2E_EMAIL and $env:E2E_PASSWORD)
```
**Adding a page in Step 12** (the pattern to copy):
1. `features/<area>/queries.ts`: a `request((api) => api.GET("/api/..."))` per read.
2. `features/<area>/components/`: async Server Components that await a query and render; a `…Skeleton` next to each.
3. `features/<area>/actions.ts`: Server Actions for changes (validate with zod, call FastAPI, `refresh()`).
4. `app/(portal)/<area>/page.tsx`: static header + `<SectionBoundary><Suspense fallback={<…Skeleton/>}><…/></Suspense></SectionBoundary>`.

### 5.2 End user: signing in
```
1. Opens http://localhost:3000/projects
2. proxy.ts: no valid cookie → redirect to /login?next=%2Fprojects
3. The login page is static: it appears instantly, and the form works even before JavaScript loads
4. Types email + password, presses Sign in → the form POSTs to the login Server Action
     zod check fails      → "That doesn't look like an email address." under the field
     FastAPI says 401     → "Wrong email or password." (same text whether the account exists or not)
     FastAPI says 429     → "Too many failed logins. Try again in N minutes."
     success              → Next.js sets the HttpOnly cookie (expires with the token, 8 h)
                            → reads ?next= from the page it was posted from → redirect to /projects
5. proxy.ts: cookie valid → the page renders
```

### 5.3 End user: the dashboard, part by part
| Part | Waits for | Shows |
|---|---|---|
| Frame, title "Dashboard", skeletons | nothing (static shell) | instantly |
| Greeting "Good to see you, Priya", account menu, admin links | `GET /api/auth/me` (once) | name, role; Resumes/Users links for admins |
| Number tiles | `GET /api/overview` + `GET /api/resumes/stats`, in parallel | active employees, searchable resumes, open roles, completed match runs |
| System health | `GET /api/health` (200 or 503, both carry a report) | API, database, Ollama version, each model installed or not |
| Resume pipeline | `GET /api/resumes/stats` | count per stage, worker running; live every 10 s while anything is in progress |
| Projects and open roles | `GET /api/projects` | roles with allocation, start date, "requirements parsed" |

If the backend is down, each card shows the reason in place; the frame and the other cards still work.

### 5.4 End user: signing out, and sessions that end
- **Sign out:** account menu → *Sign out* → the `logout` Server Action deletes the cookie and redirects to `/login`.
- **After 8 hours:** the proxy sees the expired token and sends the next page request to `/login?next=…`.
- **Account deactivated, secret changed, or forged token:** FastAPI answers 401 → `/auth/session-expired` deletes the cookie → `/login?expired=1` shows "Your session has ended. Please log in again."

---

## 6. The files

```
frontend/
├── package.json, package-lock.json     dependencies (exact versions locked), scripts
├── next.config.ts                      Cache Components, React Compiler, typed routes, headers, /api rewrite
├── tsconfig.json                       strict TypeScript (+ noUncheckedIndexedAccess)
├── eslint.config.mjs                   Next.js + React rules (incl. React Compiler checks)
├── .prettierrc.json, .prettierignore   formatting (+ Tailwind class sorting)
├── vitest.config.mts, vitest.setup.ts, vitest.empty.ts     unit tests
├── playwright.config.ts, e2e/          browser tests: auth.spec.ts, portal.spec.ts, helpers.ts
├── scripts/generate-api-types.mjs      npm run api:types
├── .env.example                        BACKEND_URL, HTTPS
├── AGENTS.md                           written by Next.js: "read node_modules/next/dist/docs first"
└── src/
    ├── proxy.ts
    ├── app/                            ROUTES
    │   ├── layout.tsx, globals.css, global-error.tsx, not-found.tsx
    │   ├── (auth)/login/page.tsx
    │   ├── auth/session-expired/route.ts
    │   └── (portal)/layout.tsx, page.tsx (dashboard), error.tsx,
    │                agent/ employees/ projects/ resumes/ users/  page.tsx (placeholders)
    ├── features/
    │   ├── auth/       actions.ts, schemas.ts, components/{login-form, account-menu, session-parts, admin-only}.tsx
    │   └── dashboard/  queries.ts, labels.ts, components/{overview-tiles, stat-tile, health-card,
    │                   pipeline-card, projects-card, greeting}.tsx
    ├── components/
    │   ├── ui/         button, input, label, card, badge, alert, skeleton, dropdown-menu
    │   ├── layout/     app-shell, nav-links, navigation, page-header
    │   ├── section-boundary.tsx, auto-refresh.tsx, coming-soon.tsx
    └── lib/
        ├── api/        client.ts, errors.ts, schema.d.ts (generated), types.ts
        ├── auth/       session.ts, constants.ts, jwt.ts, redirect.ts
        ├── env/        schema.ts, index.ts
        └── utils.ts
```

### 6.1 Foundations (`src/lib`)
| File | What it does | Why it's needed | Where in the flow | Output |
|---|---|---|---|---|
| `env/schema.ts` | zod schema for `BACKEND_URL` (http/https only, no trailing slash), `HTTPS`, `NODE_ENV`; `parseEnv()` lists every bad variable | Fail at startup with a clear message, not later with a network error | Startup; imported by `next.config.ts` too | Typed `Env` or an error naming the variable |
| `env/index.ts` | `env = parseEnv(process.env)`, marked `server-only` | Only server code may read settings | Every server module that needs a setting | `env.BACKEND_URL`, `env.HTTPS` |
| `api/schema.d.ts` | **Generated** TypeScript description of every FastAPI path and model | Types that match the backend exactly | Compile time | `paths`, `components` types |
| `api/types.ts` | Short aliases: `Overview`, `Health`, `Project`, `UserRole`, … | Readable code | Compile time | Type names |
| `api/errors.ts` | `ApiResult<T>`; `messageFromDetail()` turns FastAPI's `detail` (string or 422 list) into a sentence; `fallbackMessage(status)` | Messages people can act on | After every backend call | A string |
| `api/client.ts` | `request(call, {on401})`: read the cookie → typed client with the Bearer token → run → `ApiResult`; 401 → `/auth/session-expired`; network failure → status 0 | The **one** door to FastAPI | Every page, action, query | `{ok:true,data}` or `{ok:false,status,message}` |
| `auth/constants.ts` | Cookie name, public paths, login/home paths | One definition shared by proxy, session and actions | Everywhere auth is involved | Constants |
| `auth/jwt.ts` | `readTokenExpiry()`, `isTokenExpired()` (with 5 s slack); pure, no verification | The proxy's quick check | Proxy | true/false |
| `auth/redirect.ts` | `safeNextPath()` | Block open redirects | Login action | A same-site path or `/` |
| `auth/session.ts` | `getCurrentUser()` (`"use cache: private"`), `isAdmin()`, `setSessionCookie()`, `clearSessionCookie()` | The server-side session | Shell, pages, actions, route handler | `SessionUser` |
| `utils.ts` | `cn()` (merge Tailwind classes), `formatNumber`, `formatDate`, `firstName` | Small shared helpers | Components | Strings |

### 6.2 Routes (`src/app`)
| File | What it does and why | Output |
|---|---|---|
| `proxy.ts` | Before each page: no valid-looking cookie → `/login?next=…`; signed in and on `/login` → `/`. Skips `/api`, `/auth/*`, static files | Redirect or continue |
| `layout.tsx` | `<html lang="en-IN">`, page-title template, `noindex` (internal tool), theme colour for light/dark | The document |
| `globals.css` | OKLCH tokens (light + dark), Tailwind theme mapping, base styles, **reduced-motion** support | The look |
| `(auth)/login/page.tsx` | Static page around the form; only the "session ended" notice reads `?expired` (inside Suspense) | Sign-in page |
| `auth/session-expired/route.ts` | Route Handler: delete cookie → `/login?expired=1` | Breaks the redirect loop (4.4) |
| `(portal)/layout.tsx` | `AppShell` with two Suspense slots (role-based nav, account menu); never awaits the session itself | The frame |
| `(portal)/page.tsx` | Dashboard: static header + four `SectionBoundary > Suspense > Card` blocks | Streamed dashboard |
| `(portal)/error.tsx` | Segment error page with `retry()` and the error `digest` | Recovery UI |
| `global-error.tsx`, `not-found.tsx` | Root-crash page (own `<html>`); 404 | — |
| `(portal)/*/page.tsx` | Placeholders listing what Steps 12–13 add; Resumes and Users wrapped in `AdminOnly` | Static pages |

### 6.3 Features (`src/features`)
| File | What it does and why | Output |
|---|---|---|
| `auth/schemas.ts` | zod `loginSchema` (trim + lower-case email, required password) and `LoginState` | Validated input / form state type |
| `auth/actions.ts` | `login`: validate → `POST /api/auth/login` (401 returned, not "session ended") → set cookie → redirect to `?next=` read from the **Referer**. `logout`: tell FastAPI, delete cookie, redirect | Cookie + redirect, or errors for the form |
| `auth/components/login-form.tsx` | Client form with `useActionState`; field errors linked by `aria-describedby`; spinner while pending; keeps the typed email | The form |
| `auth/components/account-menu.tsx` | Radix dropdown: name, role, email, **Sign out** (the item calls `requestSubmit()` on a hidden form outside the menu; see finding 3) | Menu |
| `auth/components/session-parts.tsx` | `RoleNav`, `AccountSlot` (async, need the session) and their fallbacks | Shell parts |
| `auth/components/admin-only.tsx` | Renders children for admins, a clear notice for others | Gate (UX, not security) |
| `dashboard/queries.ts` | `getOverview`, `getQueueStats`, `getProjects`, `getHealth` (503 counts as data) | `ApiResult`s |
| `dashboard/labels.ts` | Pipeline stage names, "in progress" states, model labels | Constants |
| `dashboard/components/*` | Async cards + skeletons; `meter` roles on the pipeline bars | Cards |

### 6.4 Shared components (`src/components`)
| File | What it does and why |
|---|---|
| `ui/button.tsx` | `cva` variants (default, secondary, outline, ghost, destructive, link) and sizes; `asChild` puts button styles on a Link |
| `ui/input.tsx`, `ui/label.tsx` | Inputs whose red border comes from `aria-invalid` (one attribute for sight and screen readers); Radix label |
| `ui/card.tsx` | Composable `Card`, `CardHeader`, `CardTitle`, `CardAction`, `CardContent` |
| `ui/badge.tsx`, `ui/alert.tsx`, `ui/skeleton.tsx` | Status labels; messages with `role="alert"` (errors) or `role="status"` (info); loading placeholders |
| `ui/dropdown-menu.tsx` | Radix menu (arrow keys, Esc, focus return, type-ahead) with our styles |
| `layout/app-shell.tsx` | Sidebar (desktop) / top bar (mobile), **skip-to-content link**, `<nav aria-label="Main">` |
| `layout/navigation.ts` | The menu as data + `navItemsFor(role)` |
| `layout/nav-links.tsx` | Active page (`aria-current="page"`) and a pending dot via Next.js 16's `useLinkStatus` |
| `layout/page-header.tsx` | One `<h1>` + description per page |
| `section-boundary.tsx` | `catchError` boundary per section with **Try again** |
| `auto-refresh.tsx` | `router.refresh()` on an interval while the tab is visible |
| `coming-soon.tsx` | Placeholder card |

### 6.5 Backend changes (Step 11b)
| File | Change |
|---|---|
| `app/schemas/overview.py` | `HealthOut` (typed health report) and `Overview` (counts by status) |
| `app/api/overview.py` | `GET /api/overview`: `GROUP BY status` counts for employees, projects, roles, match runs, plus parsed roles |
| `app/api/health.py` | Declares `response_model=HealthOut` (also for 503) so the generated frontend types are precise |
| `app/main.py` | Registers the overview router (signed-in users); version 0.10.0 |

---

## 7. Testing strategy

| Level | Tool | What it covers here | Count |
|---|---|---|---|
| Static | TypeScript (strict), ESLint, Prettier | Types incl. generated API types and routes; React rules; formatting | `npm run check` |
| Unit | Vitest + Testing Library (jsdom) | JWT expiry, safe redirects, error messages, settings validation, login schema, role menu, Button, LoginForm (with a **fake action**) | 43 tests |
| End-to-end | Playwright + `@next/playwright` | Redirect to login with `next`; server-side validation; wrong password; login → requested page → HttpOnly cookie → sign out; forged token cleared; **login without JavaScript**; dashboard streams fully; **instant navigation** (`instant()`); active menu item; security headers | 10 tests |

Why both: Vitest can't render **async** Server Components (the Next.js testing guide says so), so anything that awaits data is covered end to end in a real browser. The `instant()` helper (enabled by `EXPOSE_TESTING_API=1` in test builds only) freezes request-time data and checks that the destination's heading appears from the prefetched shell alone.

---

## 8. TypeScript and React patterns you'll meet
| Code | Meaning |
|---|---|
| `import "server-only";` | Build error if this file ends up in browser code |
| `"use client";` / `"use server";` | This file runs in the browser too / these exports are Server Actions |
| `"use cache: private";` (first line of a function) | Cache this function's result per user, in the browser only |
| `export default async function Card() { const r = await getX(); … }` | An async Server Component: awaits data while rendering |
| `<Suspense fallback={<Skeleton/>}>…</Suspense>` | Show the fallback now; stream the content in when ready |
| `const [state, formAction, pending] = useActionState(login, {})` | Connect a form to a Server Action |
| `request((api) => api.GET("/api/overview"))` | A typed backend call; `api` is created with the token |
| `type ApiResult<T> = { ok: true; data: T } \| { ok: false; … }` | A **discriminated union**: after `if (r.ok)`, TypeScript knows `r.data` exists |
| `LayoutProps<"/">`, `PageProps<"/login">` | Types Next.js generates for each route (`next typegen`) |
| `cva(base, { variants })` + `cn(...)` | Typed style variants; merge classes with overrides |
| `<Button asChild><Link …/></Button>` | Render the child with the parent's styles and behaviour |
| `catchError(Fallback)` | Turn a fallback function into an error-boundary component |
| `z.object({...}).safeParse(x)` | Validate unknown input; `success` + `data` or `error` |

---

## 9. Alternatives, industry standard and enterprise grade
| Need | Ours | Common alternatives | Enterprise / world-class |
|---|---|---|---|
| Framework | Next.js 16 App Router, Cache Components | React Router 7 (Remix), TanStack Start, Vite SPA, Angular, Nuxt, SvelteKit | Next.js or Angular; micro-frontends for many teams |
| Data loading | Server Components + Suspense streaming | TanStack Query / SWR in client components | Server Components + a DAL; TanStack Query only for highly interactive client state |
| API client | `openapi-fetch` + `openapi-typescript` | Orval, Hey API, hand-written fetch | Generated clients + contract tests in CI |
| Mutations | Server Actions + zod | API routes + React Hook Form | Server Actions + shared zod schemas + optimistic UI (`useOptimistic`) |
| Components | shadcn/ui conventions on Radix | MUI, Mantine, Chakra, Ant Design, React Aria | A company design system (Fluent, Carbon, Atlassian) with Storybook and visual tests |
| Auth | Backend JWT in an HttpOnly cookie, forwarded by the BFF | Auth.js, Clerk, Better Auth | OIDC single sign-on (Entra ID, Okta); BFF holds tokens; refresh tokens; revocation |
| CSP | Header without nonces (keeps static shell) | Nonce CSP via proxy | Nonce or hash (SRI) CSP + CSP violation reporting |
| Tests | Vitest + Playwright | Jest, Cypress | + accessibility (axe), visual regression, CI on every pull request |
| Observability | Server log, error digests | Sentry | OpenTelemetry (Next.js `instrumentation.ts`), real-user monitoring |
| Hosting | `next start` on the PC | Docker behind a reverse proxy | Kubernetes / Azure App Service / Vercel, CDN, WAF |

---

## 10. Findings while building version 2
1. **`Math.random()` during prerendering (build error).** A shared `openapi-fetch` client with an auth middleware generated a random request ID *before* the cookie was read, so Next.js saw randomness while building the static shell. Fix: read `cookies()` first, then create a middleware-free client per request. **Lesson:** under Cache Components, touch request data before anything non-deterministic, and let the build tell you.
2. **`localhost:8010` passed URL validation.** It's a valid URL whose *scheme* is `localhost:`. A unit test caught it; the settings now require `http` or `https`.
3. **Sign out did nothing (Playwright).** Radix renders an open menu in a **portal** at the end of `<body>`, so the submit button was no longer inside its `<form>`. The first fix (`form={id}` on the button) was *still* broken: Radix closes the menu on click and removes the button before the browser submits. That was only found in Step 12, when the confirm dialogs failed the same way. Final fix: the item calls `formRef.current?.requestSubmit()`. Sign-out is now covered by the passing browser suite.
4. **Login without JavaScript failed (Playwright).** Streamed Suspense content is revealed by a script, so a form inside `<Suspense>` stays hidden without JavaScript. Fix: the form is static; `?next=` is read by the Server Action from the Referer, and only the "session ended" notice streams.
5. **A test matched two "alerts".** Next.js adds an empty `role="alert"` element that announces page changes. Tests filter by text.
6. **The old error page used `reset()`.** Next.js 16 passes `retry()`, which re-fetches on the server; `reset()` only re-renders in the browser and can't recover from a server error.
7. **Version 1's dashboard downloaded up to 500 employees to count them.** Replaced by `GET /api/overview`.

## 11. Limitations
- `'unsafe-inline'` scripts in the CSP (trade-off in 4.7).
- The session lives up to 5 minutes in the browser's router cache: a role change shows in the menu after the next full load (the backend enforces the new role immediately). Switching accounts in the same tab without a reload has not been tested yet.
- Health and pipeline refresh by polling every 10 s (only while busy), not push. A `/bff` SSE relay like Step 13's could replace it.
- Sign-out doesn't revoke the JWT (stateless tokens, Step 9); deleting the cookie ends it in this browser.
- English only; an accessibility audit with a screen reader and axe is still to do (semantic HTML, labels, skip link, focus rings, reduced motion and ARIA roles are in place).
- The rewrite's backend address is fixed at build time (`BACKEND_URL` before `npm run build`); the `/bff` relay reads it at run time.

## 12. Tested
**In a sandbox (stand-in models, a copy of your real database):** `npm run check` clean (types, lint, formatting, 43 unit tests); production build with every route **◐ Partial Prerender**; `/api/overview` and the typed `/api/health` responses; Playwright 7 of 10 on the first run, with the failures traced to findings 3–5. After the Step 12 fixes the whole suite passes (15/15, including the Step 12 tests; see doc 16).

**On your PC:** pending your `npm run check`, `npm run build` and browser run. Results will be added to doc 07.

## 13. Glossary
| Term | Meaning |
|---|---|
| **Server / Client Component** | Rendered only on the server / also interactive in the browser (`"use client"`) |
| **Static shell** | The prerendered part of a page that is served instantly |
| **Partial Prerender (◐)** | A route with a static shell plus streamed dynamic parts |
| **Suspense / fallback** | A boundary that shows a placeholder until its content is ready |
| **Streaming** | Sending HTML in pieces as each part finishes |
| **Server Action** | A server function usable as a form action |
| **DAL (Data Access Layer)** | The server-only code that fetches data, checks access, returns small objects |
| **DTO** | A small object with only the fields the UI needs (`SessionUser`) |
| **BFF / rewrite** | Backend-for-frontend; forwarding `/api` to FastAPI |
| **Proxy** | Next.js code before each request (formerly "middleware") |
| **HttpOnly / SameSite** | Cookie flags: unreadable by page JS / not sent with cross-site posts |
| **CSP** | Content-Security-Policy: the browser's allow-list for scripts, styles, connections |
| **CSRF / XSS / clickjacking / open redirect** | Forged cross-site requests / injected scripts / a page inside a hidden frame / a link that bounces to another site |
| **Radix / shadcn/ui** | Accessible unstyled primitives / owned component source built on them |
| **Design token / OKLCH** | A named design value / a colour format where numbers match perceived lightness |
| **React Compiler** | Automatically memoises components (no manual `useMemo`) |
| **Progressive enhancement** | The page works with plain HTML first; JavaScript makes it nicer |
| **Hydration** | The browser attaching React to server-rendered HTML |
