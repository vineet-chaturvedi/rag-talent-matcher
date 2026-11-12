# 08 · Troubleshooting

Every problem met so far, how to recognise it, why it happens and how to fix it. Start with the quick checks; then find your symptom below.

---

## 1. Quick checks (run these first)

| # | Check | Command / place | Good result |
|---|---|---|---|
| 1 | Right folder, venv active | Prompt shows `(.venv) PS ...\backend>` | Both present |
| 2 | Not an admin shell | Prompt does **not** start in `C:\WINDOWS\system32` | Normal user |
| 3 | Code imports cleanly | `python -c "import app.main"` | No output |
| 4 | Ollama sees the models | `ollama list` | nomic-embed-text, qwen2.5:3b, qwen2.5:7b |
| 5 | Server healthy | http://127.0.0.1:8010/api/health | `"status": "ok"` |
| 5b | Portal healthy | `cd frontend; npm run check` | All green; then http://localhost:3000 shows the login page |
| 6 | Pipeline state | http://127.0.0.1:8010/api/resumes/stats | Nothing stuck; `worker_running: true` |
| 7 | Server log | The terminal running `uvicorn` | No red tracebacks |

**Reading a traceback:** start at the **last line** (the actual error), then read upwards to find the first file under `app\` (where our code was involved).

---

## 2. Starting the server

### `[WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions`
- **Cause:** Windows reserves blocks of ports for Hyper-V / WSL / Docker (the `winnat` service). Port 8000 was inside one.
- **Check:** `netsh interface ipv4 show excludedportrange protocol=tcp`
- **Fix:** use another port: `uvicorn app.main:app --port 8010`. Alternatively, as admin: `net stop winnat` then `net start winnat`; this may move the reserved ranges, and they can change again after a reboot.

### `Error loading ASGI app. Could not import module "app.main"`
- **Cause:** `app\main.py` doesn't exist under that exact name: missing, in the wrong folder, or saved as `main.py.txt` (Explorer hides extensions).
- **Check:** `Get-ChildItem -Recurse -File -Exclude *.pyc | Where-Object { $_.FullName -notlike "*\.venv\*" } | Select-Object FullName`
- **Fix:** rename or move the file; turn on Explorer → View → **File name extensions**; create files in the IDE.

### `ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed`
- **Cause:** newer SQLAlchemy versions install greenlet only on request.
- **Fix:** `sqlalchemy[asyncio]>=2.0.30` in `requirements.txt`, then `pip install -r requirements.txt`.

### `ModuleNotFoundError: No module named 'app'` (or `'fastapi'`)
- **Cause:** not in `backend\`, or the venv isn't active.
- **Fix:** `cd ...\backend` and `.\.venv\Scripts\Activate.ps1`.

### `running scripts is disabled on this system` when activating the venv
- **Fix (once):** `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

---

## 3. Ollama and models

### `/api/health` says `degraded` and every model shows `installed: false`
- **Cause:** Ollama is reading an empty model folder. Here, `setx OLLAMA_MODELS` was run while Ollama was running, and the Ollama app also has its own **Model location** setting.
- **Fix:** Ollama app → Settings → **Model location** = `D:\OllamaModels` → quit and restart Ollama → remove the env variable (`[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $null, "User")`) → `ollama list`.

### `/api/health` returns 503 "Cannot connect to Ollama"
- **Fix:** start Ollama from the Start menu (llama icon in the tray). The worker resumes automatically within 30 seconds.

### Folder size shows 6.41 GB instead of ~6.9 GB
- Not a problem: PowerShell's `1GB` is a binary gigabyte (1,073,741,824 bytes).

### Resumes stay `parsed` with "Waiting for Ollama"
- Ollama is not running or not reachable. Start it; attempts are not used up while waiting.

### The first search or extraction is slow, later ones fast
- **Cold start:** the model is loaded from disk into RAM on first use (~2 s for embeddings, 4–10 s for LLMs) and kept for 5 minutes. Normal.

---

## 4. Files and scripts

### `No module named scripts.try_search` (or any new script)
- **Cause:** a zip was extracted into a new sub-folder (Windows "Extract All" creates `step6_files\backend\...`) instead of over the project.
- **Check:** `Test-Path scripts\try_search.py`
- **Fix:** from the project root: `Expand-Archive -Path "$env:USERPROFILE\Downloads\stepN_files.zip" -DestinationPath . -Force`, or `robocopy "..\stepN_files\backend" "." /E`.

### `python -m scripts.upload_samples` fails to connect
- The server must be running (in another terminal) on port 8010.

### Upload says "This exact file was already uploaded"
- The SHA-256 fingerprint matches an existing resume. Intended. Delete the old resume first if you really want to re-upload it.

### A resume is `failed` with "needs OCR"
- It is a scanned image with no text layer. OCR is not implemented yet; upload a text-based PDF or DOCX.

---

## 5. Processing and results

### A long extraction or match run keeps restarting / "Stopped because the server shut down"
- **Cause:** `--reload` restarts the server whenever a `.py` file is saved, cancelling the running LLM call (this also happened when code was updated during a Step 8 run).
- **Fix:** run long jobs without `--reload`.

### Profiles still show old, inflated numbers after a code change
- Extraction results are stored; code changes don't alter existing profiles.
- **Fix:** `POST /api/resumes/reextract` (LLM again) or `POST /api/resumes/reembed` (chunks and vectors only).

### Search results look stale or include an old resume version
- Search ignores non-current and non-ready resumes. If in doubt, rebuild the index: `POST /api/resumes/reembed`.

### `MissingGreenlet` error
- **Cause:** async SQLAlchemy tried to lazily load a relationship that wasn't loaded in the query.
- **Fix:** add `selectinload(Model.relationship)` to the query, or `await session.refresh(obj)` after a commit.

### `sqlite3.OperationalError: database is locked`
- Two writers at the same moment beyond the 5-second busy timeout; usually a script and the server both writing. Stop one and retry.

---

## 6. Login and permissions (Step 9)

### Every request returns `401 {"detail": "Not logged in."}`
- **Cause:** since Step 9 every endpoint except `/api/health` and `/api/auth/*` needs a login.
- **Fix:** in `/docs` click **Authorize** (username = your email). In scripts set `$env:RTM_EMAIL` and `$env:RTM_PASSWORD`, or type them when asked. With `curl`/`Invoke-RestMethod`, send `Authorization: Bearer <token>` from `POST /api/auth/login`.

### `401 "Your session has expired"` or everyone is logged out after a restart
- **Cause:** the token is older than `ACCESS_TOKEN_MINUTES` (8 h), or `JWT_SECRET` is empty, so a new random development secret was made at startup (the log warns about it).
- **Fix:** log in again; put a permanent secret in `.env`: `python -m scripts.create_user --secret`.

### `403 "This action needs the role: admin."`
- You're logged in as a resource manager. Uploads, imports, retry/delete, re-extract, re-embed, users and dev tools are admin-only. Ask an admin, or use an admin account.

### `429 "Too many failed logins. Try again in N minutes."`
- 5 wrong passwords for that email within 15 minutes. Wait, or restart the server (the counter is in memory). An admin can reset the password with `PATCH /api/users/{id}`.

### No admin exists / "No portal users yet" in the log
- **Fix:** `python -m scripts.create_user --role admin --email admin@company.local --name "Portal Admin"` (works with the server stopped or running).

### `ModuleNotFoundError: No module named 'pwdlib'` or `'jwt'`
- **Fix:** `pip install -r requirements.txt` (Step 9 added `pwdlib[argon2]` and `PyJWT`).

### `RuntimeError: JWT_SECRET must be set in production`
- With `ENVIRONMENT=production` the server refuses to start without a secret. Add `JWT_SECRET=...` to `.env`.


---

## 6b. The web portal (Step 11)

**Where to look first:** the portal's own server log, i.e. the terminal running `npm run dev` / `npm run start`. In production the browser only shows a generic message and a **Reference** (digest); the same digest appears next to the real error in that terminal.

### `npm` or `npx` is not recognised
- Node.js isn't on the PATH in this terminal. Close and reopen the IDE terminal after installing Node; check `node -v` (22 or newer, see `engines` in `package.json`).

### The portal won't start: `Invalid frontend settings (.env.local): - BACKEND_URL: ...`
- A setting failed validation (`src/lib/env/schema.ts`). The line names the variable. Typical: `BACKEND_URL=localhost:8010` without `http://` (it is technically a URL whose scheme is `localhost:`, so it is rejected on purpose). Fix `.env.local`, restart.

### A card says "Cannot reach the backend. Is FastAPI running (uvicorn on port 8010)…?"
- The Next.js **server** can't reach FastAPI (pages call it server-to-server). Start `uvicorn app.main:app --port 8010` in `backend/`, or fix `BACKEND_URL`. The rest of the page keeps working; refresh when the backend is up.
- "The backend had a problem…" instead: FastAPI answered 5xx. The traceback is in the **uvicorn** terminal.

### "System health" shows `error` but the other cards work
- Expected when Ollama is not running: `/api/health` answers 503 with a report, and the card shows which part failed (database or Ollama). Start Ollama (`ollama serve` or the tray app).

### Every page sends me back to the login page
- The cookie is missing or expired (8 hours): log in again.
- Open the portal on one host name only (`http://localhost:3000`): cookies for `localhost` and `127.0.0.1` are different.
- `HTTPS=true` in `.env.local` while using `http://`: the browser drops a `Secure` cookie on plain HTTP outside `localhost`. Set `HTTPS=false`.

### The login page says "Your session has ended. Please log in again." right after I logged in earlier
- FastAPI rejected the token: `JWT_SECRET` changed (or isn't set, so a restart made a new one), the account was deactivated, or the token was tampered with. The portal deleted the cookie via `/auth/session-expired`. Log in again; set a fixed `JWT_SECRET` in `backend/.env`.

### Login shows "Too many attempts…" / "Too many failed logins. Try again in N minutes."
- 5 wrong passwords for one email within 15 minutes (Step 9 lockout). Wait, or restart the backend (the counter is in memory). Running the browser tests with a wrong `E2E_PASSWORD` can trigger this.

### Admins don't see "Resumes" / "Users" in the menu
- The menu depends on the role from `/api/auth/me`. Check the account menu's role line. A role changed by an admin shows after a full page reload (the session is cached in the browser for a few minutes; the backend applies the change immediately).

### `npm run build` fails with "Next.js encountered the unstable value `Math.random()` (or `Date.now()`) while prerendering"
- Some code produced a random value or the time before reading request data, while Next.js was building the static shell. Read `cookies()`/`searchParams` first (as `request()` does), move the part into a `<Suspense>` boundary with request data, or mark a value with `"use cache"`. The message names the file and line.

### `npm run build` fails because uncached data or `cookies()` is accessed outside `<Suspense>` (a "blocking route")
- A component that reads the session or calls the backend isn't inside a `<Suspense>` boundary. Wrap it (see the dashboard page for the pattern). Never `await` the session at the top of a layout.

### Build error mentioning `server-only` ("…only works in a Server Component")
- A Client Component (`"use client"`) imports a server module (`lib/api/client`, `lib/auth/session`, `lib/env`, `features/*/queries`). Load the data in a Server Component and pass plain values as props. For types only, use `import type`, which is erased and allowed.

### TypeScript errors in many files after a backend change
- Intended: the generated types changed (`npm run api:types`). Each error is a place that must follow the new API shape. If you did NOT change the backend, regenerate against the running backend; the file must never be edited by hand.

### `npm run api:types` says "Could not read http://127.0.0.1:8010/openapi.json"
- Start the backend first; check `BACKEND_URL`.

### The dev overlay shows an "Insight" about instant navigation or a segment dropped from rendering
- A layout or component withheld `{children}` or read request data outside `<Suspense>`. A layout must always render its children; let only the user-specific parts wait inside their own boundaries (doc 07, Step 11).

### `npm run test:e2e` problems
- `Executable doesn't exist … chromium`: run `npx playwright install chromium` once.
- Most tests "skipped": set `$env:E2E_EMAIL` and `$env:E2E_PASSWORD` in the same terminal.
- Port 3100 busy: `$env:E2E_PORT="3200"`. A failure leaves a recording: `npx playwright show-trace test-results\...\trace.zip`.

### The browser console shows "Refused to … because it violates the Content Security Policy"
- The CSP in `next.config.ts` only allows this site's own scripts, styles, images and connections. If a new feature really needs another origin (e.g. a company font server), add exactly that origin to the right directive; don't remove the policy.

### `npm run build`: "`usePathname()` (or `useSearchParams()`) in a Client Component outside of `<Suspense>`"
- A Client Component reads the URL in the prerendered shell; often a **Suspense fallback** does it (fallbacks are part of the shell). On dynamic routes like `/employees/[id]` the URL isn't known at build time. Give the fallback a version without the hook (see `NavLinksStatic`), or wrap the component in its own `<Suspense>`.

### A confirm dialog or menu item does nothing when clicked
- Radix renders dialogs and menus in a portal and closes them on click, which removes a submit button before the browser submits. Submit the form in code: `formRef.current?.requestSubmit()` (see `ActionButton`, `AccountMenu`).

### Upload says "This exact file was already uploaded (resume id N)"
- Same bytes as a stored resume (SHA-256 match). Nothing to do; or delete the old version first if you really want to re-process it (better: *Re-extract all* or *Retry*).

### Upload says "No employee with code 'X'"
- Bulk upload finds the employee from the file name's first part (`EMP-1001_anything.pdf`). Rename the file, import the employee via the HR CSV first, or upload on the employee's page (any file name works there).

### The resume list or a profile page doesn't update
- It refreshes itself every 5 s only while a resume on screen is being processed and the tab is visible. Otherwise reload. If statuses never move: is the worker running (dashboard "worker running")? Is Ollama up?

### Employee page says "No AI profile yet"
- The current resume hasn't reached "Profile ready" (see its status in "Resume versions"), or it failed (reason shown there; admins can Retry).

### Education shows no year
- The year is only shown if it appears on the resume's line for that institution (the model's own guesses are not trusted, Step 12a finding). Check the resume text.

### "Read the description with AI" takes a minute, or fails with "Cannot connect to Ollama" / an unusable answer
- Parsing uses the quality model (qwen2.5:7b): 30-60 s on a CPU is normal; the button shows progress. 503 = Ollama isn't running. 502 = the model returned JSON that doesn't fit the schema: try again, or correct the requirements by hand.

### A match run finds nobody ("Nobody matched")
- Only employees with a **Searchable** (ready) current resume are eligible. Check `/resumes` (are resumes stuck in "Profile ready" or "Indexing"? Is the worker running?). With "Only people who can take the role's allocation" ticked, also check availability.

### A match run stays at "Judging…"
- The judge reads about one resume per minute on a CPU; the page updates itself. If the backend restarted during the run, the run is marked failed at the next start ("Stopped because the server shut down"): start a new run. Use `uvicorn` without `--reload` for long AI work (a file save restarts the server).

### A judge quote has a "?" ("not found in the resume")
- Code could not find the quoted words in the resume text, so the claim isn't trusted: a "yes" without a found quote counts as "partly" (Step 8). Read the resume to decide.

### Saving requirements changed the skill names or merged two skills
- Intended: names are normalised to the skill catalogue ("k8s" → "Kubernetes"), and duplicates are merged (the new minimum years are kept).

### "You can't deactivate yourself or remove your own admin role"
- Intended (Step 12c): ask another admin. If you are the only admin, create a second admin first (Users → New account, role Administrator).

### "This is the last active admin; create another admin first."
- The portal must always have an active admin. Create or reactivate another admin, then change this one.

### A deactivated person still sees a page
- Deactivation takes effect at their next action: every API call reloads the user, gets 401, and the portal sends them to the login page.

### "A user with this email already exists."
- Emails are unique without regard to capitals. Find the existing (maybe deactivated) account in the list and reactivate it instead.

### Port 3000 is already in use
- Another dev server is running. Stop it, or `npx next dev --port 3001`.

### Styles look broken or old pages appear after pulling changes
- Stop the dev server, delete `frontend\.next`, run `npm run dev` again.

### After updating to Step 11b: imports of `@/components/ui` or `@/lib/api` fail
- Leftover version-1 files. They were moved to `rag-talent-matcher\_to_delete\frontend-v1\`; make sure none remain in `frontend\src` (`session-provider.tsx`, `app-shell.tsx`, `components/ui/index.tsx`, `lib/api.ts`, `lib/types.ts`, `(portal)/dashboard.tsx`, `(auth)/login/login-form.tsx`).

---

## 6c. The staffing assistant chat (Step 13)

### The answer appears all at once at the end instead of word by word
- Something between the browser and FastAPI is buffering the stream. The portal's relay (`/bff/agent/…`) already sends `Cache-Control: no-cache, no-transform` and `X-Accel-Buffering: no`. Check that you're on the current code: the chat must call `/bff/agent/{id}`, **not** `/api/agent/…` (the `/api` rewrite compresses with gzip, and that holds everything back; Step 13 finding). Behind your own nginx or proxy, turn off buffering and compression for `/bff/`. In Chrome dev tools → Network → the request → **EventStream** you should see events arrive one by one.

### Only "Thinking…" for a minute or more
- Normal on a CPU: the 7B model reads the question and the tools before its first step (30–120 s per answer). If nothing appears for over 3 minutes, check that Ollama is running (`ollama ps`) and see the backend log.

### "The assistant could not answer: Cannot connect to Ollama"
- Start Ollama (`ollama serve`, or the tray app), then ask again. The question is saved; the failed answer is not.

### "The connection ended before the answer finished."
- The stream stopped without a final event: the backend restarted (e.g. `--reload` after a code change), the PC slept, or the network dropped. Ask again; there is no automatic resume yet (doc 17, limitations).

### A step shows a red ✗
- That tool failed (e.g. an unknown employee code). The agent sees the error too and usually tries something else or explains. The line after the → is the tool's own message.

### Old conversations show steps without the "→ …" line
- Conversations saved before Step 13's backend change, or a backend not yet restarted. Restart uvicorn; new and old tool messages then get their summary when loaded.

### Asking a question sends me to "Your session has ended"
- The token expired during the chat (the relay got 401). Log in again; the conversation is still there.

### `Module not found: Can't resolve 'react-markdown'`
- New packages in Step 13: run `npm install` in `frontend/`.

## 6d. Step 15: PostgreSQL, storage, queues, workers, Docker (doc 21)

### After pulling Step 15: `ModuleNotFoundError: No module named 'alembic'` (or `asyncpg`)
- New libraries: `pip install -r requirements.txt` (and `-r requirements-cloud.txt` if you use cloud models, buckets or queues). Then refresh your lock file: `pip freeze | Out-File -Encoding utf8 requirements.lock.txt`.

### First start after Step 15: "Database from before migrations: … stamping revision 0001"
- Expected, once. Your SQLite database is recognised, given the missing columns, marked as migration `0001`, then upgraded to the latest. Your data is untouched. From now on, schema changes arrive as migrations.

### "The database is at migration 0001, the code needs 0002"
- `DB_AUTO_MIGRATE=false` and the schema is behind: run `alembic upgrade head` from `backend/` (or the compose `migrate` service), then start again.

### `relation "resume_chunks" does not exist` / `extension "vector" is not available` (PostgreSQL)
- The migrations didn't run: `alembic upgrade head`.
- The pgvector extension isn't installed on the server:
  - **Docker:** use the `pgvector/pgvector:pg16` image.
  - **Azure:** add `VECTOR` to the server parameter `azure.extensions`.
  - **RDS and Cloud SQL:** they support it; the migration enables it.

### Uploads fail with 503 "The file could not be stored"
- **Local:** the API can't write to `UPLOAD_DIR` (permission, full disk, read-only volume).
- **Cloud:** the bucket or container name, credentials, or IAM role. The message says which. Run `python -m scripts.migrate_files --check` to see which stored files are reachable.

### Resumes stay "Queued" with `WORKER_ENABLED=false`
- No worker is running. Start one: `python -m app.worker` (or the compose `worker` service). The dashboard shows "no worker running" / "N workers running".

### A resume or match run continues after a few minutes on its own
- Its worker stopped (closed, crashed, redeployed). After `WORKER_LEASE_SECONDS` (5 minutes by default) another worker takes it over. That's the safety net, not a bug. After `WORKER_MAX_ATTEMPTS` failures it is marked failed with the reason.

### Docker: the portal says "Ollama is not reachable", but Ollama runs on this PC
- Containers reach your PC as `host.docker.internal`, and Ollama on Windows listens only on 127.0.0.1 by default. Fix:
  1. Set the user environment variable `OLLAMA_HOST=0.0.0.0` (System Properties → Environment Variables).
  2. Quit Ollama from the tray and start it again.
  3. Allow it through Windows Firewall for private networks.
- Your models stay where they are (`OLLAMA_MODELS=D:\OllamaModels`).

### Docker: `docker compose up` stops with "Set POSTGRES_PASSWORD in .env"
- `cp .env.docker.example .env` next to `docker-compose.yml`, then fill in `POSTGRES_PASSWORD` and `JWT_SECRET`.

### Docker: login works on http://localhost:3000 but not from another computer
- Cookies over plain HTTP work on localhost. For other computers, put HTTPS in front (a reverse proxy or the cloud's load balancer), set `HTTPS=true`, and rebuild the portal image: `HTTPS` is a build argument.

## 7. Environment hygiene

| Habit | Why |
|---|---|
| Use the IDE terminal (normal user), not an admin PowerShell | Admin shells can create files your normal user can't edit, and run untrusted package code with full rights |
| Never commit `.env` or `data/` | Secrets (`JWT_SECRET`) and personal data (resumes) |
| Commit after every working step | Easy to roll back |
| Keep `requirements.lock.txt` updated | Reproduce a working setup exactly |
