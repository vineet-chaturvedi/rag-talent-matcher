# 16 · Step 12 Explained: The Admin Portal Pages

Step 12 turns the portal from a dashboard into a working tool: the knowledge base (employees and their resumes), projects and matching, and user management. This document explains **why** each page exists, the **patterns** every page follows, **every file**, the **developer and end-user flows**, what the **browser tests found**, and the **alternatives** up to enterprise level.

Step 12 is built in three parts:

| Part | Pages | Status |
|---|---|---|
| **12a** | Employees (list, search, profile), Resumes (upload, pipeline, maintenance) | ✅ Built and tested (this document) |
| **12b** | Projects and matching (roles, AI-parsed requirements, match runs, judge verdicts) | ✅ Built and tested (section 10) |
| **12c** | Users (create, role, deactivate, reset password) + your own Account page | ✅ Built (section 11; tests deferred) |

**Read first:** doc 15 (the frontend architecture these pages are built on).

---

## 1. Why these pages

| Who | Needs to | Page |
|---|---|---|
| Admin | Load people from HR, add resumes, see what the AI pipeline is doing, fix failures | `/employees` (import), `/resumes` |
| Resource manager | Find people, check availability, see what someone really knows (with evidence) | `/employees`, `/employees/[id]` |
| Both | Trust the AI's output | The profile page shows **every skill with a quote from the resume** |

> **The knowledge base is only as good as what you can see and correct. Step 12a makes the RAG system's input visible: who is in it, which resumes were read, what the AI extracted (with proof), and what failed and why.**

---

## 2. The patterns every Step 12 page follows

These are the rules from doc 15, applied to real pages. Once you know them, every new page looks the same.

### 2.1 Static header, streamed data
```tsx
export default function EmployeesPage(props: PageProps<"/employees">) {
  return (
    <>
      <PageHeader title="Employees" … />                       // static: instant
      <SectionBoundary title="The employee list">              // a crash stays inside this box
        <Suspense fallback={<EmployeesTableSkeleton />}>       // grey rows until the data arrives
          <EmployeeList searchParams={props.searchParams} />   // async: reads the URL, calls FastAPI
        </Suspense>
      </SectionBoundary>
    </>
  );
}
```

### 2.2 The URL is the state
Search text, filters and page number live in the URL: `/employees?q=python&availability=available&page=2`.

| Why | Effect |
|---|---|
| Shareable | Send a colleague the exact filtered list |
| Survives reload and Back | No lost filters |
| Works without JavaScript | Filters are a GET `<Form>` (from `next/form`) and links |
| Server-rendered | The server reads the URL and fetches exactly that page |

URL values are **untrusted** (anyone can type `?page=-4&availability=<script>`), so `lib/search-params.ts` turns them into valid values or defaults. A broken link shows page 1, never an error.

### 2.3 Reads in `queries.ts`, changes in `actions.ts`, files from the browser
| Kind of work | Where | How | Why |
|---|---|---|---|
| Read data | `features/<area>/queries.ts` (server-only) | `request((api) => api.GET(...))` | Typed, token forwarded, `ApiResult` |
| Small change (retry, delete, re-index) | `features/<area>/actions.ts` (`"use server"`) | Server Action → FastAPI → `refresh()` | Works as a plain form; the page re-renders with the new state |
| Send a file (resume, CSV) | Client Component + `lib/api/browser.ts` | `fetch` to `/api/...` through the rewrite | A Server Action's body is limited to 1 MB and would pass every file through Next.js's memory; the rewrite streams it to FastAPI |

### 2.4 One button = one Server Action, with an optional confirmation
```tsx
<ActionButton action={retryResume.bind(null, resume.id)} label="Retry" pendingLabel="Retrying…" />
<ActionButton action={deleteResume.bind(null, resume.id)} label="Delete" pendingLabel="Deleting…"
              confirm={{ title: "Delete …?", description: "…can't be undone.", confirmLabel: "Delete resume" }} />
```
- `action.bind(null, id)`: a Server Action with the id filled in. Next.js encrypts bound values in the page; the action still validates the id, because every Server Action is a public endpoint.
- The result ("Queued again.", or FastAPI's error) appears next to the button (`role="status"`, so screen readers announce it).
- Destructive actions open a **Radix AlertDialog**: focus moves into it and is trapped, Esc cancels, and focus returns to the button afterwards.

### 2.5 Roles: hide for clarity, enforce in FastAPI
- `AdminOnly` wraps a whole page section with a notice for non-admins (Resumes page).
- `IfAdmin` shows a part (upload box, retry/delete buttons, CSV import) only to admins, and nothing to others.
- Neither is security: FastAPI answers 403 to a resource manager calling an admin endpoint, whatever the page shows.

### 2.6 Live pages without WebSockets
While any resume on the screen is being processed, `<AutoRefresh seconds={5} />` re-renders the page's Server Components (`router.refresh()`), only while the tab is visible. When nothing is in progress, nothing is polled.

---

## 3. The pages

### 3.1 `/employees`: the list
- Search (code, name, department or location), plus an availability filter (available, partly allocated, fully allocated, on leave).
- Table: name and code (links to the profile), designation and department, location, availability (with "from 1 Nov 2026" when not free), and the current resume's pipeline status.
- 25 per page. The backend has no total count, so the page asks for 26: if 26 come back, there is a next page (the "limit + 1" trick).
- Admins: an **Import from HR** card (CSV). It shows created and updated counts, and every skipped row with its line number and reason.

### 3.2 `/employees/[id]`: the profile
- HR facts (department, location, manager, email, joined, current project, availability).
- **The AI profile** of the current resume: headline, summary, total years, which model extracted it, and any warnings from the extraction checks.
- **Skills table:** years, last used, and **the quote from the resume** that supports each skill. This is the RAG system's "show your evidence" principle made visible: a resource manager can see *why* the system believes someone knows Django, and spot a wrong extraction.
- Experience timeline, education and certifications.
- **Resume versions:** newest first, numbered (v1, v2 …), with the current one marked, plus page count, status and errors. Admins can upload a new version, retry or delete.
  - An older version says **"Older version · not searched"**, not "Searchable": it is kept as history, but its chunks were removed from both search indexes when the newer version arrived.
- **The original files (admins, added 2026-11-06):** "Open" and "Download" next to the current resume in the page header, and on every version, including older ones. The `/resumes` list has them too.
  - How the file travels: the browser asks the Route Handler `/bff/resumes/{id}/file`. It reads the login cookie on the server and calls FastAPI `GET /api/resumes/{id}/file` with a Bearer token, then streams the bytes back unchanged. This is the same relay pattern as the agent chat (doc 17).
  - PDFs open in the browser's own viewer in a new tab. Word files (.docx/.doc) download, because browsers can't display them.
  - **Why admins only:** the original contains the phone number, email and address that the profile, the search index (anonymised chunks) and the agent deliberately leave out. Resource managers see the profile and its evidence quotes instead.
  - **Where files live:** `backend/data/uploads/<EMPLOYEE_CODE>/<first 16 characters of the SHA-256>.<ext>`. Every version is kept; the database row holds the original name, size, type and hash.
- A non-number or unknown id → the 404 page.

### 3.3 `/resumes` (admins): the intake
- **Upload:** drag and drop (or choose) many PDF/DOCX files named `EMP-1001_name.pdf`. Each file gets its own line: waiting, uploading, ✓ queued, or ✗ with the reason (wrong type, too big, duplicate, unknown employee code).
- **Current resumes:** status filter chips with counts (All, Queued, …, Failed), and per row the employee, file, size and pages, status with the error and attempts, and when uploaded. Actions: Retry (failed resumes) and Delete (with confirmation). The list refreshes itself while anything is in progress.
- **Maintenance:** *Re-extract all* (the LLM reads everything again, slow) and *Re-index all* (rebuild chunks and vectors, fast), both confirmed first. They only queue work; the worker does it in the background.

---

## 4. The flows

### 4.1 End user: an admin loads the knowledge base
```
1. /employees → Import from HR → choose employees.csv → Import
     browser ──POST /api/employees/import (rewrite, cookie)──▶ FastAPI: create/update by employee_code
     ◀── "12 created, 4 updated, 1 row skipped: Line 9 (EMP-1017): full_name is required"
     router.refresh() → the list shows the new people
2. /resumes → drop 40 files
     each file (2 at a time) ──POST /api/resumes/bulk──▶ FastAPI: check type and content, find the
       employee from the file name, store, queue          ◀── ✓ queued / ✗ reason, per file
     router.refresh() → "Current resumes" shows them as Queued
3. The background worker (Steps 3-6) takes each resume: Reading file → Text ready → AI reading →
   Profile ready → Indexing → Searchable. The list updates itself every 5 s while that happens.
4. A scanned PDF fails ("needs OCR"): visible under Failed, with the reason. Fix the file, upload again.
```

### 4.2 End user: a resource manager checks a person
```
/employees → search "kubernetes" (matches department/location/name; skill search is the matching
page's job, Step 12b) → filter "Available" → open Arjun Reddy → skills with years and quotes →
experience → decide whether to propose him for a role.
```

### 4.3 Developer: adding a page like these
1. Backend: make sure every endpoint the page reads has a `response_model` (the frontend types come from it). Restart, then `npm run api:types`.
2. `features/<area>/queries.ts`: one function per read.
3. `features/<area>/components/`: async Server Components plus a skeleton each; pure helpers in their own `.ts` file with a `.test.ts`.
4. `features/<area>/actions.ts`: Server Actions that validate input, call FastAPI, `refresh()` and return an `ActionResult`.
5. `app/(portal)/<area>/page.tsx`: static header, then `SectionBoundary > Suspense > component`.
6. A read-only e2e test in `e2e/`, then `npm run check`, `npm run build`, `npm run test:e2e`.

---

## 5. The files

### 5.1 Backend changes
| File | Change | Why |
|---|---|---|
| `app/schemas/resume.py` | `ResumeListItem` (adds `employee_code`, `employee_name`), `RequeueResult` | The admin list must say whose resume it is; typed responses for re-extract/re-index |
| `app/api/resumes.py` | `GET /api/resumes` returns `ResumeListItem` (employees loaded with `selectinload`: one extra query per page, not one per row); typed `RequeueResult`; profile education cleaned on read | No N+1 queries; exact frontend types |
| `app/api/employees.py` | `?availability=` filter | "Who is free?" is the most common question |
| `app/schemas/profile.py` | `EducationOut` instead of `dict` | Typed education entries in the frontend |
| `app/extraction/postprocess.py` | `ground_education()`: the year must appear on the resume's line for that institution | Data-quality finding 4 in section 7 |

### 5.2 Shared frontend pieces (new)
| File | What it does | Output |
|---|---|---|
| `lib/search-params.ts` | `pageParam`, `enumParam`, `textParam`, `idParam`: untrusted URL values → valid values or defaults | Safe numbers/strings |
| `lib/actions.ts` | `ActionResult` type, `toActionResult()` | What Server Actions return to buttons |
| `lib/api/browser.ts` | Typed client for browser code (`baseUrl: ""` → the `/api` rewrite); `browserErrorMessage()` (401 → session-expired) | Uploads from the browser |
| `lib/utils.ts` (+) | `formatDateTime` (UTC from FastAPI → local), `formatBytes`, `plural` | Readable values |
| `components/ui/table.tsx` | Real `<table>` parts, horizontally scrollable on phones | Tables |
| `components/ui/alert-dialog.tsx` | Radix confirmation dialog | Safe destructive actions |
| `components/ui/native-select.tsx` | Styled native `<select>` (works in GET forms without JS) | Filters |
| `components/action-button.tsx` | Button → one Server Action, pending state, result message, optional confirm | Retry/Delete/Maintenance |
| `components/pagination.tsx` | Previous/Next links that keep the other URL parameters | Paging |
| `components/empty-state.tsx` | "Nothing here, and what to do" | Empty lists |
| `features/auth/components/if-admin.tsx` | Render children for admins, nothing for others | Admin-only parts |
| `components/layout/nav-links.tsx` (changed) | `NavLinksStatic` for the loading fallback (no URL hook) | Finding 1 in section 7 |

### 5.3 Resumes feature (`features/resumes/`)
| File | What it does |
|---|---|
| `labels.ts` | Pipeline stages with labels and tones, `IN_PROGRESS`, `isInProgress()`: one definition used by the dashboard, lists and badges |
| `queries.ts` | `listResumes({status, page})`, `getQueueStats()` (moved here from the dashboard) |
| `actions.ts` | `retryResume`, `deleteResume`, `reextractAll`, `reembedAll` (validate, call FastAPI, `refresh()`) |
| `upload.ts` (+ test) | `precheckFile` (type, empty, 10 MB), `employeeCodeFromFilename` (same rule as the backend), `runWithConcurrency` (at most N uploads at once) |
| `components/bulk-upload.tsx` | Drop zone, per-file states, one request per file, 2 in parallel, `router.refresh()` at the end |
| `components/resumes-table.tsx` | The admin list with actions, auto-refresh and pagination |
| `components/status-filter.tsx` | Filter chips with counts, as links |
| `components/resume-status-badge.tsx` | Status label (spinner while processing) |
| `components/maintenance-card.tsx` | Re-extract all / Re-index all with confirmations |

### 5.4 Employees feature (`features/employees/`)
| File | What it does |
|---|---|
| `labels.ts` | Availability values, labels, tones |
| `queries.ts` | `listEmployees`, `getEmployee`, `getProfile` |
| `components/employee-filters.tsx` | Search + availability as a `next/form` GET form |
| `components/employees-table.tsx` | The list, empty states, pagination |
| `components/availability-badge.tsx` | "Partly allocated · 50%" etc. |
| `components/employee-header.tsx` | HR facts (`EmployeeFacts`) |
| `components/profile-sections.tsx` | Summary + warnings, skills with evidence, experience timeline, education and certifications; clear message when there is no profile yet |
| `components/resume-history.tsx` | Versions, status, admin actions, upload a new version |
| `components/import-csv.tsx` | HR CSV upload with the row-by-row result |
| `components/upload-resume.tsx` | One new resume for one employee |

### 5.5 Routes
| File | Route |
|---|---|
| `app/(portal)/employees/page.tsx` | `/employees` |
| `app/(portal)/employees/[id]/page.tsx` | `/employees/7` (dynamic segment; `PageProps<"/employees/[id]">`) |
| `app/(portal)/resumes/page.tsx` | `/resumes` (admins) |

### 5.6 Tests
| File | Covers |
|---|---|
| `lib/search-params.test.ts` | Bad pages, unknown filter values, long text, bad ids |
| `features/resumes/upload.test.ts` | File checks, the code-from-filename rule, concurrency limit |
| `lib/utils.test.ts` | Bytes, plurals, UTC time handling |
| `e2e/knowledge-base.spec.ts` | Search kept in the URL; broken URL parameters; profile page; unknown id → 404; resume status filters. **Read-only**: safe against your real data |

---

## 6. Tested
In the sandbox (stand-in models, a copy of your database; uploads and deletes only there):
- `npm run check`: types, lint, formatting and **58 unit tests** pass. Production build: every route ◐ Partial Prerender, including `/employees/[id]`.
- Playwright: **15 of 15** pass (auth, dashboard, instant navigation, security headers, and the 5 new tests).
- Manual browser script: 16 employees; search "ananya" → 1; "available" → 10; broken parameters → normal list; Ananya's profile (11 skills with quotes, 3 jobs, education); unknown and non-numeric ids → 404.
- Upload test with 4 files: the new version was queued; the duplicate got "This exact file was already uploaded (resume id 3)."; the unknown code got "No employee with code 'EMP-9999'…"; `notes.txt` got "Only PDF and DOCX files are accepted." (checked in the browser, before any upload).
- Delete with confirmation removed the row; *Re-index all* reported "13 resumes queued for re-indexing."; no browser console errors.

---

## 7. Findings
1. **The build failed on the first dynamic route:** "`usePathname()` in a Client Component outside of `<Suspense>`" on `/employees/[id]`. The menu's *loading fallback* used the URL hook, and a fallback is part of the prerendered shell, where a dynamic route's URL isn't known yet. Fix: `NavLinksStatic` (same list, no URL) for the fallback. **Lesson:** fallbacks must not read request data.
2. **Confirmed deletes did nothing.** The dialog's button was a submit button for a form outside the dialog. Radix closes the dialog on click and removes the button *before* the browser submits, so no request was sent. The account menu's *Sign out* had the same flaw (the Step 11b `form=` fix had not been re-tested in a browser). Fix: both call `form.requestSubmit()` in code. The full Playwright suite now covers sign-out and passes. **Lesson:** don't count a fix as done until a browser test has exercised it.
3. **Next.js 16 keeps the previous page in the DOM (hidden)** so Back is instant. A test that looked for the label "Search" also found the dashboard's hidden "Searchable" bar. Tests use exact roles (`getByRole("searchbox", { name: "Search" })`).
4. **Data quality: 12 of 14 stored education years were not years.** The 3B model wrote "goes with the date 2014", "context.year", "goes here", "goes to null if not provided in the resume". It never invented a wrong year, but often gave none although the resume had one ("…, Pune University, 2017"). Fix in the spirit of "LLM reads, code checks": `ground_education()` takes the year from the resume line naming the institution (or the next line, for wrapped PDF text), and keeps the model's year only if it appears there. Result: **14 of 14 correct**; an invented year (2099) is dropped. Applied when profiles are built and, because it is idempotent, when old profiles are read. Visible only because the profile page shows the data. **Lesson:** a UI on AI output is also a data-quality tool.
5. **"1 pages"**, found on the screenshot: now `plural()`.
6. **Changes in your folder that I didn't make:** `.nvmrc` (26), the `engines` range in `package.json`, and `browsing-topics` removed from the Permissions-Policy in `next.config.ts`, all dated 12:27. They were kept as they are (my working copy was synced to them). Chrome warns about `browsing-topics` as an unknown feature, which may be why it was removed.

## 8. Alternatives and enterprise grade
| Need | Ours | Common alternatives | Enterprise |
|---|---|---|---|
| Tables | Hand-composed `<table>` + server pagination | TanStack Table (sorting, column visibility), AG Grid | AG Grid / virtualised tables for 100k rows, saved views, column filters, CSV export |
| Pagination | Offset + "limit + 1" | Total counts (`X-Total-Count`), cursor pagination | Cursor (keyset) pagination: stable under inserts, fast on huge tables |
| Uploads | Browser → rewrite → FastAPI, one file per request | Uppy, react-dropzone | Direct-to-object-storage uploads (pre-signed S3/Azure Blob URLs), virus scanning, resumable uploads (tus) |
| Live status | `router.refresh()` polling while busy | SWR/TanStack Query `refetchInterval` | Server-Sent Events or WebSockets from a job queue (Celery/Arq/Temporal events) |
| Confirmations | Radix AlertDialog | Native `confirm()` (blocking, ugly) | Undo instead of confirm (soft delete + "Undo" toast) for reversible actions |
| Search | SQL `ILIKE` on code/name/department/location | PostgreSQL full-text, Meilisearch | OpenSearch/Elasticsearch; the matching page (12b) covers skill and semantic search |
| Data quality | Grounding checks + visible evidence | Validation rules in the pipeline | Human review queue for low-confidence extractions, extraction-accuracy dashboards |

## 9. Limitations
- No skill search on the employee list (by design: the matching page, 12b, ranks by skills with evidence).
- Polling every 5 s while busy; with thousands of resumes in progress a push channel would be better.
- Delete is permanent (no soft delete or undo).
- The CSV import shows the first 20 skipped rows.
- Education years in stored profiles are fixed on read; a full *Re-extract all* (doc 07, action item 1) also stores clean values.

---

## 10. Part 12b: Projects and matching

### 10.1 Why this is the most important page set
Everything built in Steps 3-8 meets the person here. A resource manager writes a role in plain language. The AI turns it into requirements (Step 7), and the person checks and **corrects** them. Retrieval and rule scoring rank people in about a second (Steps 7-8). Then the LLM judge reads the top resumes and gives a verdict per must-have, with quotes that **code** checked against the resume (Step 8).

> **The matching pages make every number explainable: for each person you see which must-haves were found (with years and the resume sentence), which are missing, how the score was computed, and what the judge said, with a check mark only where its quote really is in the resume.**

### 10.2 The pages
| Route | What it shows | What you can do |
|---|---|---|
| `/projects` | Every project with its roles (open roles first): allocation, headcount, location, start, "requirements ready" or "not read yet", status | Create a project |
| `/projects/[id]` | The project and its roles | Add a role (title, **description**, location, start, allocation, headcount, minimum years) |
| `/roles/[id]` | Description; **requirements** (must-haves and nice-to-haves with minimum years, seniority, minimum total years, location, domain, search summary, who parsed it, "corrected by a person"); earlier runs | AI-read the description; correct the requirements; start a match; mark filled / close / reopen |
| `/match-runs/[id]` | Progress while the judge works; the requirements the run used; ranked candidates | Open a candidate's profile; read the evidence |

### 10.2b Feedback on the cards (Step 14c)
Every candidate card ends with **"Was this right? 👍 👎"**. 👎 opens a reason list and a note, and the card shows the team's count. Admins see all ratings on the new **Feedback** page (`/feedback`), with filters. The buttons are a small Client Component (`features/feedback/components/feedback-buttons.tsx`) that calls Server Actions and keeps its own state, so the long results page doesn't re-render on a click. See doc 19, section 10.

### 10.3 One candidate card, explained
| Part | Comes from | Why it is there |
|---|---|---|
| Rank, name, final score | `match_results` | The answer |
| "Judge: strong/good/partial/weak", summary | `explanation.judge` | The LLM's overall impression (it does NOT set the score; code does) |
| "available" / "availability conflict" + note | `explanation.facts.availability` | "100% free now (role needs 50%)" or "only 30% free; available from 15 Dec 2026" |
| Must-haves: found / missing, "via Amazon EKS" | `facts.must_matched` / `must_missing` (Step 7) | Which requirement each skill covers, including implied skills, with years and last use |
| Skills, Relevance, Rule score, Judge score bars | `score_breakdown` (Step 8) | `final = 0.6 × rule + 0.4 × judge` and the factors (experience, availability, location), so nothing is a black box |
| The judge's assessment (open for the top 3) | `judge.must_haves`, `strengths`, `gaps` | Per must-have: Met / Partly / Not met plus the quote; ✓ = **found in the resume by code**, ? = not found. When the model said "yes" but its quote wasn't found, the card says so ("the model said yes…"): that requirement only counts as "partly" |
| Where the keywords matched | `facts.keyword_snippets` (FTS5) | The exact resume text that matched, highlighted |
| Model, seconds, tokens | `judge.stats` | Cost and audit |

The page shows **only what the run stored**. Rerun later with changed requirements and the old run still shows exactly what was decided at the time, which is the audit trail Step 8 designed.

### 10.4 The flows
**End user: staffing a role**
```
/projects → New project ("Retail Platform Migration") → its page → Add a role:
  "Platform engineer to migrate 60 services to Kubernetes on AWS with Terraform and CI/CD…"
→ /roles/6: "Read the description with AI" (30-60 s; the button shows progress)
    → Must have: Kubernetes, Terraform, CI/CD, AWS · Nice to have: Helm, ArgoCD, Prometheus, Grafana
→ Correct: move Terraform to nice-to-have, add "k8s" with 3 years
    → saved as "Kubernetes · 3+ y" (normalised and merged with the existing entry), "corrected by a person"
→ Find best matches (10 candidates, judge reads 5) → /match-runs/29 appears at once with the ranking
→ every ~5 s the page updates: "The AI judge has read 2 of 5 resumes…"; verdicts appear card by card
→ at the end the judged top 5 are re-ranked by their final score
→ open the top person's profile, talk to them and their manager → "Mark filled"
```

**Developer: what happens on "Find best matches"**
```
<form action={startMatch.bind(null, roleId)}>  (Server Action, zod-validated: 1-50 candidates, judge 0-20)
  → POST /api/roles/6/match  (FastAPI: retrieval + rule scoring, ~1 s; judge task started in background) → 202
  → redirect("/match-runs/29")
/match-runs/29 (Server Component) → GET /api/match-runs/29 → RunProgress + ResultCards
  while status = "running": <AutoRefresh seconds={5}/> → router.refresh() → the same GET, fresh data
```

### 10.5 Files (12b)
**Backend**
| File | Change | Why |
|---|---|---|
| `app/schemas/matching.py` | Typed models for the stored JSON: `ScoreBreakdown`, `RetrievalFacts`, `AvailabilityFacts`, `JudgeVerdictOut` (with `MustHaveVerdictOut`, `StrengthOut`, `JudgeStats`), `Explanation`, `MatchRunSettings`; `MatchRunSummary` gains `top_names`, `judge_top_n`, `result_count` | The portal gets exact types instead of `dict`. Defaults keep older stored runs valid: **all 9 runs / 90 results on your PC, including the 26 real judge verdicts, validated with 0 errors** |
| `app/api/matching.py` | Fills the new summary fields; tolerates empty JSON | History list with names |
| `app/schemas/project.py` | `RoleUpdate` (all fields optional) | Partial updates |
| `app/api/projects.py` | `GET /api/projects/{id}`, `PATCH /api/roles/{id}` | A project page; mark a role filled/closed; editing details doesn't silently re-parse |

**Frontend: `features/projects/`**
| File | What it does |
|---|---|
| `queries.ts` | `listProjects`, `getProject`, `getRole`, `listMatchRuns`, `getMatchRun` |
| `schemas.ts` (+ test) | zod schemas for project, role, requirements and match forms; `intWithDefault` (an emptied number field means "default", not 0); `FormState`, `formValues` |
| `actions.ts` | `createProject` and `createRole` (redirect to the new page), `setRoleStatus`, `parseRequirements`, `saveRequirements` (JSON payload, validated), `startMatch` (redirect to the run) |
| `labels.ts` | Project, role and run statuses, judge rating and met/partly/not-met tones, seniority list |
| `components/project-list.tsx`, `role-row.tsx`, `role-status-badge.tsx` | Projects with roles, open first |
| `components/new-project-form.tsx`, `new-role-form.tsx`, `match-form.tsx` | `useActionState` forms; values kept after an error; server-side messages |
| `components/requirements-panel.tsx` | View and edit modes: chips with minimum years; move a skill between must and nice; add/remove; seniority, years, location, domain, search summary; AI read / read again (with confirmation) |
| `components/run-progress.tsx` | Status, "judge has read N of M", progress bar, auto-refresh while running |
| `components/result-card.tsx`, `score-bar.tsx` | The candidate card (10.3) |
| `components/run-history.tsx` | Earlier runs: date, status, how many ranked/judged, top names |

**Shared (new):** `components/form-field.tsx` (label + control + hint + error, wired with `aria-describedby`), `components/submit-button.tsx` (`useFormStatus`: a button that knows its form is submitting), `components/ui/textarea.tsx`. **Changed:** `navigation.ts` (`also` prefixes and `isActive()`: the Projects item stays marked on `/roles/…` and `/match-runs/…`), `nav-links.tsx` uses `isActive`.

**Routes:** `app/(portal)/projects/page.tsx`, `projects/[id]/page.tsx`, `roles/[id]/page.tsx`, `match-runs/[id]/page.tsx`.

**Tests:** `features/projects/schemas.test.ts` (11), `navigation.test.ts` (+2), `e2e/matching.spec.ts` (5, read-only: never creates, parses or runs anything on your real backend).

### 10.6 Tested
- `npm run check`: **69 unit tests** pass; production build: every route ◐, including the three new dynamic ones.
- Playwright: **20 of 20** pass.
- Full journey in a real browser (stand-in models, copy of your data): server-side validation messages and kept values; project → role → AI parse (4 must-haves, 4 nice-to-haves) → correction (Terraform moved, "k8s" → Kubernetes 3+ y, merged) → match with 6 candidates and judge 3 → live progress → completed; Priya Nair first (Kubernetes 6.2 y, CI/CD via Jenkins, AWS via Amazon EKS); role history; "Mark filled"; 404s for unknown ids; no console errors.

### 10.7 Findings (12b)
1. **An emptied number field became 0.** `z.coerce.number("")` is `0`, so clearing "Headcount" failed "minimum 1" instead of using the default. Found by a unit test; `intWithDefault()` treats "" as "not given".
2. **The browser's own validation hid our messages.** `minLength={20}` on the description made the browser block the submit with a generic tooltip, so the clearer server message ("…the AI reads this text") never appeared. The forms now use `noValidate` (like the login form) and keep the attributes for phone keyboards and screen readers.
3. **Typing old data without breaking it.** The match JSON grew over Steps 7-8. Typed models with defaults validated every stored run, including your 26 real verdicts, before the API changed.
4. **Correcting requirements merges duplicates.** Adding "k8s" when "Kubernetes" is already a must-have keeps one "Kubernetes" with the new minimum years (FastAPI's normalisation). That's intended, and visible right after saving.
5. **Tests that count must wait.** `locator.count()` doesn't wait for streamed content, so two tests silently skipped until they waited for the loading skeleton to disappear. Lesson: a skipped test is a result to read, not a pass.

### 10.8 Alternatives and enterprise grade (matching UI)
| Need | Ours | Enterprise |
|---|---|---|
| Long AI work | Background task + page polling | A job queue (Celery/Arq/Temporal) with push updates (SSE/WebSocket), retries and cancellation |
| Explainability | Stored facts, score parts, verified quotes | Same, plus reviewer feedback ("good match / bad match") stored to evaluate and tune (Step 14) |
| Requirement editing | JSON payload validated by zod | A skills taxonomy picker (ESCO/O*NET, company catalogue) with autocomplete |
| Decisions | "Mark filled" | Shortlists, approvals by the employee's manager, HRIS/ERP sync of allocations |
| Fairness | Human makes the decision; names hidden from chunks | Bias audits of rankings, documented model cards, EU AI Act / NYC LL 144 style assessments for employment-related AI |

---

## 11. Part 12c: Users and your account

### 11.1 Why
Step 9 built secure logins, but accounts could only be created with `python -m scripts.create_user`. A portal used by a team needs admins to manage access themselves, safely and with history kept:

| Who | Needs to | Where |
|---|---|---|
| Admin | Give a new colleague access, change roles, cut off a leaver, help someone who forgot their password | `/users` |
| Everyone | Change their own password | `/account` (account menu → "Account and password") |

### 11.2 The rules (and who enforces them)
| Rule | Why | Enforced by |
|---|---|---|
| Only admins manage accounts | Access control is a privilege | FastAPI `require_admin` (the page also shows "Administrators only") |
| Accounts are **deactivated, never deleted** | "Who ran this match?", "who uploaded this resume?" must stay answerable | FastAPI (no delete endpoint) |
| The last active admin can't be demoted or deactivated | Otherwise nobody could manage the portal | FastAPI (Step 9) |
| **No admin can deactivate or demote themselves** (new) | An accidental click must not lock you out; another admin can still do it | FastAPI (Step 12c) + no such buttons on your own row |
| Passwords: at least 12 characters, no leading/trailing spaces, no forced symbols | NIST SP 800-63B: length beats complexity rules, which push people to "Password1!" | FastAPI `password_problem()` + the same rule in zod for instant messages |
| Unique email (case-insensitive) | One person = one account | FastAPI (409) |
| Passwords never travel back to the page | A password in HTML or a form state could leak | The Server Actions strip every `*password*` field from returned values |
| Deactivation takes effect on the person's next action | Every request reloads the user from the database (Step 9) | FastAPI `get_current_user` |

### 11.3 The pages
**`/users` (admins)**
- Accounts: name and email ("you" on your own row), role, status, created; active accounts first.
- Per account (not your own): **Reset password** (a dialog with a show/hide password field), **Make admin** (with a confirmation that explains what admins can do) or **Make resource manager**, **Deactivate** (confirmation: history kept, can be undone) or **Reactivate**.
- **New account:** name, email, role (with an explanation of both roles), first password. The success message reminds you to share the password in person or by phone, not by email.

**`/account` (everyone)**
- Who you are signed in as (name, email, role).
- **Change password:** current password (proves it's you), new password twice. Messages per field: wrong current password, too short, the two don't match, same as the old one.

### 11.4 Flows
**An admin onboards a resource manager**
```
/users → New account: "Meera Pillai", meera@company.local, Resource manager, a 12+ character password
  → Server Action createUser: zod check → POST /api/users (FastAPI: admin? unique email? password policy?
    Argon2id hash) → 201 → refresh(): Meera appears in the list
  → "Meera Pillai can now sign in as meera@company.local. Share the password … not by email."
Meera signs in → account menu → Account and password → changes it to her own.
```
**Someone leaves the company**
```
/users → their row → Deactivate → confirm → PATCH /api/users/7 {is_active: false}
  → their next request gets 401 (the user is reloaded from the database on every call) → login page
  → their match runs and uploads keep their name.
```

### 11.5 Files (12c)
| File | What it does |
|---|---|
| `backend/app/api/users.py` | New safeguard: 409 "You can't deactivate yourself or remove your own admin role. Ask another admin." |
| `lib/forms.ts` | `FormState` and `formValues()` moved here from the projects feature: shared by every feature (`features/projects/schemas.ts` re-exports them) |
| `components/ui/dialog.tsx` | Radix Dialog (focus trap, Esc, close button) for small forms |
| `features/users/schemas.ts` | zod: `createUserSchema`, `resetPasswordSchema`, `changePasswordSchema` (two new passwords must match and differ from the current one); `MIN_PASSWORD_LENGTH = 12`; role labels |
| `features/users/queries.ts` | `listUsers()` |
| `features/users/actions.ts` | `createUser`, `setUserRole`, `setUserActive`, `resetPassword`, `changeOwnPassword`; passwords stripped from returned values; a wrong current password is shown next to that field |
| `features/users/components/users-table.tsx` | The account list with per-row actions (none on your own row) |
| `features/users/components/new-user-form.tsx` | Create an account |
| `features/users/components/reset-password-dialog.tsx` | Admin sets a new password (form and button inside the dialog, so a normal submit works) |
| `features/users/components/change-password-form.tsx` | Your own password |
| `features/users/components/password-field.tsx` | Password input with show/hide (`aria-pressed`) |
| `features/auth/components/account-menu.tsx` | New "Account and password" item |
| `app/(portal)/users/page.tsx`, `app/(portal)/account/page.tsx` | The two routes |

### 11.6 Checked, and not yet tested
- **Checked:** TypeScript, ESLint and Prettier clean; production build with `/users` and `/account` as ◐ Partial Prerender; the backend safeguard returns 409 when an admin tries to deactivate themselves (curl against the stand-in backend).
- **Not yet tested (deferred at your request):** no unit tests for the users schemas, no browser tests and no browser run of these pages. Worth adding before relying on them: password rules and the "passwords must match" check (unit); create → appears in list; deactivate → that user's session ends; reset password → new password works; no actions on your own row (browser, against a test database, because these tests change accounts).

### 11.7 Alternatives and enterprise grade
| Need | Ours | Enterprise |
|---|---|---|
| Accounts | Local users with Argon2id passwords | Single sign-on (OIDC/SAML with Entra ID, Okta, Google Workspace); accounts and leavers come from HR/IdP provisioning (SCIM) |
| Onboarding | Admin sets a first password | Invitation email with a one-time link; must set a password on first login |
| Forgot password | An admin resets it | Self-service reset by email link with expiry, or none at all with SSO |
| Second factor | None | MFA (TOTP, passkeys/WebAuthn), enforced for admins at least |
| Sessions | Stateless JWT, 8 h | Short access tokens + refresh tokens, revocation list, "sign out everywhere" |
| Audit | "By" columns on runs and uploads | An audit log of every account change (who changed whose role, when) |
| Roles | Two fixed roles | Role-based access with permissions, groups from the IdP, per-project scopes |
