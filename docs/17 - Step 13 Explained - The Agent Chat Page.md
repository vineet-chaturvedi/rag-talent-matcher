# 17 · Step 13 Explained: The Agent Chat Page

Step 13 gives the staffing agent from Step 10 (doc 14) a face. A resource manager types a question in plain language. The page shows every step the agent takes while it happens: which tool it calls, with which arguments, and what came back. Then the answer streams in word by word. Earlier conversations are kept, can be continued, and can be deleted.

This document explains why the page is built this way, every new file, the developer and end-user flows, the streaming finding that changed the design, and the alternatives up to enterprise grade.

**Read first:** 14 (Step 10, the agent and its event protocol), 15 (Step 11, the frontend architecture) and 16 (Step 12, page patterns). **Next:** Step 14 (evaluation and hardening).

---

## 1. Why this page, and why it streams

The matching pages (Step 12b) answer one fixed question: who fits this role? Staffing conversations are messier. People ask "who could lead a Kubernetes migration from December?", then "and which of them is in Pune?", then "show me Priya's profile". The agent answers questions like these by calling the same read-only tools the portal uses.

On this machine a local 7B model on a CPU needs **30 seconds to 2 minutes** per answer. A page that shows a spinner for 90 seconds feels broken. A page that shows "Searching for matching people: Kubernetes, AWS → 5 found", and then the answer growing word by word, feels like work is being done. The person can also judge the result. **Showing the steps is a trust feature, not decoration.** The answer is only as good as the data the tools returned, and the person can see that data.

| Without streaming | With streaming (Step 13) |
|---|---|
| A spinner for 30–120 s | The first step appears within seconds |
| A paragraph to trust blindly | Each tool call and its result are visible |
| Stopping means closing the tab (the agent keeps running) | **Stop** aborts the request, and FastAPI stops the agent |

---

## 2. The finding that shaped the design: the rewrite buffers streams

The plan from Step 11 was simple. The browser calls `/api/agent/...` and the Next.js rewrite forwards it to FastAPI. Before building on that plan, we measured it. A tiny test server (`slow_sse.py`) sent 7 events 0.7 s apart, and a script timed when each one reached the client:

| Path | Response | When the chunks arrived |
|---|---|---|
| `/api/...` (rewrite) | `Content-Encoding: gzip` | **all at 4.2 s**: nothing, then everything at once |
| `/bff/...` (Route Handler, `Cache-Control: no-transform`) | not compressed | 0.0, 0.7, 1.4, 2.1, 2.8, 3.5, 4.2 s: **live** |

**Why:** Next.js compresses responses. A compressor collects input until it has enough to compress well, so it holds back a slow trickle of small events until the stream ends. The rewrite gives us no place to change that per route. A Route Handler that returns its own `Response` can send `Cache-Control: no-cache, no-transform`. "No-transform" tells the compression layer, and any proxy in between, to pass the bytes through untouched.

**Lesson:** "it streams" has to be measured at the client, with timestamps. Looking at the final result can't show buffering, because the text is identical either way. The same issue appears behind nginx (`X-Accel-Buffering: no`), corporate proxies and some CDNs. That's why the relay sends both headers.

So the design became the following.

```
Browser (Chat component)                    Next.js server                          FastAPI
  │ POST /bff/agent/7  {content}  ─────────▶ route.ts
  │   (cookie sent automatically)            ├─ validate id + question (zod)
  │                                          ├─ read HttpOnly cookie → Bearer token
  │                                          └─ fetch POST /api/agent/conversations/7/messages ─▶ agent loop
  │                                                {content, stream:true}, signal=request.signal     │ tools, Ollama
  │ ◀── text/event-stream, no-transform ──── return new Response(upstream.body) ◀── SSE events ───┘
  │   data: {"type":"tool_call",...}
  │   data: {"type":"tool_result",...}
  │   data: {"type":"token","text":"Priya"} ...
  │   data: {"type":"answer",...}
  │ Stop → AbortController.abort() ───────▶ request.signal aborts ──────────────▶ client gone → agent stops
```

After this step, the `/api` rewrite serves only **resume uploads** (Step 12a), which are not streamed back.

---

## 3. Concepts used in this step

### 3.1 Server-Sent Events (SSE)
SSE is a plain HTTP response that stays open. The server writes events as text, each one ending with a blank line:
```
data: {"type":"token","text":"Priya "}

data: {"type":"token","text":"Nair "}

```
SSE is one-way (server → browser), works through ordinary proxies, and needs no special server. That makes it the standard for LLM token streaming, and OpenAI, Anthropic and Ollama's own API all use it. WebSockets are two-way, which a chat doesn't need: the question goes in a normal POST.

### 3.2 Why `fetch` + a stream reader, not `EventSource`
The browser's built-in `EventSource` can only make **GET** requests without a body, and it reconnects automatically, which would ask the question again. We need a POST with the question in the body and full control over stopping. So the chat uses `fetch()` and reads `response.body`, a `ReadableStream`, piped through `TextDecoderStream` (bytes → text).

### 3.3 Chunks are not events
The network delivers bytes in arbitrary pieces. One chunk can hold three events, or half of one. `createSseParser()` keeps a buffer, cuts off every complete event (everything before a `\n\n`), and keeps the unfinished rest for the next chunk. A broken JSON event is skipped instead of breaking the whole answer. This is the most common streaming bug, and it's why the parser is a separate, pure function.

### 3.4 Route Handlers as a "backend for frontend" (BFF)
`src/app/bff/agent/[id]/route.ts` is server code in the Next.js app that answers one URL. Here it's a relay. It reads the HttpOnly cookie on the server, so browser JavaScript never sees the token. It checks the input, calls FastAPI with `Authorization: Bearer …`, and passes the stream through. The proxy (`proxy.ts`) skips `/bff`. A redirect to the HTML login page would be useless to `fetch()`, so the handler answers 401 as JSON and the chat reacts to it.

### 3.5 Cancellation end to end
`AbortController` in the browser → the browser closes the connection → Next.js aborts `request.signal` → the `fetch` to FastAPI is cancelled → Starlette notices the client is gone and stops the agent's generator. No tokens are generated for an answer nobody reads. Leaving the page also aborts (an effect cleanup).

### 3.6 Optimistic UI and `history.replaceState`
A new conversation exists only after the first question, so there are no empty conversations. On the first question, a Server Action creates it, and `window.history.replaceState(null, "", "/agent/7")` changes the URL **without a reload**. Next.js 16 keeps its router in sync with `replaceState`, so the address is shareable and Back works, and the streaming chat stays mounted.

### 3.7 One shape for live and stored answers
FastAPI stores messages (user, assistant with tool calls, tool results, the final assistant answer). The live stream sends events. Both are converted into the same **`Turn`** type (question, steps, answer, status), so a reloaded conversation looks exactly like the live one. For that, the backend now adds the same one-line `summary` to stored tool messages that the live stream showed.

---

## 4. The files

### 4.1 Backend (3 small changes)

| File | Change | Why |
|---|---|---|
| `app/agent/loop.py` | `_summary` → `summarise_tool_result` (public) | The API reuses it for stored messages |
| `app/schemas/agent.py` | `MessageOut.summary: str \| None` | Stored tool steps show "→ 5 found: EMP-1003…" after a reload, like the live view |
| `app/api/agent.py` | `_message_out()` adds the summary to tool messages; `GET /conversations/{id}` returns messages sorted by id | One source of truth for the step text; a stable order |

No new endpoint was needed: Step 10 already built the streaming one.

### 4.2 Frontend

```
src/app/bff/agent/[id]/route.ts          The streaming relay (section 3.4)
src/app/(portal)/agent/page.tsx          New conversation: the chat, nothing to load (instant shell)
src/app/(portal)/agent/[id]/page.tsx     A stored conversation: loads it, Delete button, the chat to continue
src/proxy.ts                             The matcher skips /bff (JSON 401 instead of a login redirect)
src/features/agent/
├── events.ts                            AgentEvent type (hand-written: OpenAPI can't describe a stream),
│                                        createSseParser(), tool names → human labels
├── transcript.ts                        Step/Turn types; messagesToTurns(); describeArguments();
│                                        linkEmployeeCodes() (EMP-1003 → link to the employee)
├── queries.ts                           listConversations(), getConversation()  (server-only)
├── actions.ts                           createConversation(), deleteConversation(), refreshConversations()
└── components/
    ├── chat.tsx                         Client: sends, streams, Stop, composer, suggestions, live region
    ├── turn-view.tsx                    One turn: question bubble, steps with icons, Markdown answer
    ├── markdown.tsx                     react-markdown + GFM tables; internal links via <Link>
    ├── conversation-list.tsx            Server: my conversations, newest first; current one marked
    └── agent-layout.tsx                 The two-column frame (list hidden on small screens)
src/lib/api/types.ts, schema.d.ts       Conversation, ConversationDetail, AgentMessage (+ summary)
package.json                             react-markdown, remark-gfm
```

**Why each piece is where it is:**
- **`events.ts` and `transcript.ts` are pure** (no React, no network), so they can be unit-tested with plain strings.
- **`chat.tsx` is the only Client Component** with logic. The pages, the conversation list and the data loading stay on the server, following the rule from doc 15.
- **Asking is not a Server Action.** Server Actions return one result at the end. An answer that streams for minutes needs a Route Handler. Creating, deleting and refreshing are short, so they're Server Actions.
- **Markdown:** the model answers in Markdown (lists, bold names, sometimes tables). `react-markdown` renders it **without** `dangerouslySetInnerHTML`: raw HTML in the model's text is not executed. That matters, because LLM output is untrusted input.

### 4.3 What a turn looks like

```
                                         ┌────────────────────────────────┐
                                         │ Who knows Kubernetes and AWS?  │   ← question
                                         └────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────────┐
│ ✓ Searching for matching people · must_have: Kubernetes, AWS · top_k: 3  │   ← step (spinner while running,
│   → 3 found: EMP-1003, EMP-1013, EMP-1006                                │     ✗ red if the tool failed)
│ ──────────────────────────────────────────────────────────────────────── │
│ Top matches: EMP-1003 Priya Nair (100% free now) …                       │   ← answer (codes are links)
│ 1 step · 74.1 s                                                          │   ← footer when done
└──────────────────────────────────────────────────────────────────────────┘
```

Statuses: **streaming** (steps update, answer grows, blinking cursor) → **done** (footer), or **error** (a red alert with FastAPI's message), or **stopped** ("Stopped. Ask again to get a full answer."). A step still running when the turn ended is shown as "not finished", not as a spinner forever.

Text that streams **before** a tool call is the model thinking aloud ("Let me search…"). The chat clears it when the tool call arrives, so only the final answer remains, which is also what FastAPI stores.

---

### 4.4 Rating an answer (Step 14c)
Every finished answer ends with **"Was this right? 👍 👎"** (with a reason after 👎).
- **Live answers:** the stream's `answer` event now carries `message_id`, the saved answer's id. The backend flushes the answer to the database before sending the event, so a live answer can be rated straight away.
- **Stored answers:** they get the id from the conversation, along with your earlier rating (`feedback` on the message).
- **Privacy:** only you can rate your answers. Admins see the question and the answer on the Feedback page, because that's what turns a bad answer into a new test case (doc 19, 10.4).

## 5. The flows

### 5.1 End user: asking a new question
1. **Staffing assistant** in the menu → `/agent`. With no conversation yet, three example questions are shown. Clicking one asks it.
2. Type a question, then **Enter** (Shift+Enter adds a new line; Enter is ignored while an input method is composing, e.g. Hindi or Japanese).
3. The question appears at once. The URL becomes `/agent/7`. "Thinking…" shows.
4. A step appears: **Searching for matching people · must_have: Kubernetes, AWS**, with a spinner, then ✓ and "→ 5 found: …".
5. The answer streams in. Employee codes are links to the employee page.
6. The footer shows "2 steps · 74 s". The sidebar shows the conversation, titled with the first question.

### 5.2 End user: follow-ups, stopping, coming back
- **Follow-up:** "And which of them is in Pune?" FastAPI sends the agent the whole history, so "them" works. (The fake-backend test showed the history growing: "history turns=6".)
- **Stop:** the Send button becomes **Stop** while it works. Stopping keeps the steps done so far and marks the turn as stopped.
- **Coming back:** pick a conversation in the left column. Stored steps and answers look like the live ones. An answer that was interrupted (tab closed, server restarted) says so.
- **Delete:** the button top right, with a confirmation; you return to `/agent`. Only conversation messages are deleted; match runs and profiles are not.
- **Session expired mid-chat:** the relay answers 401, and the page goes to the "session ended" login.
- **Screen readers:** a polite live region announces "Searching for matching people…" and "The answer is ready."; the turn is `aria-busy` while streaming.

### 5.3 Developer: what happens on one question
```
Chat.ask(text)
 ├─ (first question) await createConversation(text)        Server Action → POST /api/agent/conversations
 │     history.replaceState → /agent/{id}
 ├─ fetch("/bff/agent/{id}", POST {content}, signal)        → route.ts → FastAPI (stream:true)
 ├─ response.body.pipeThrough(TextDecoderStream()).getReader()
 │    loop: chunk → parse(chunk) → AgentEvent[] → apply(event) → setTurns(...)
 │       tool_call → add step (running) │ tool_result → ok/failed + summary
 │       token → answer += text         │ answer → done, seconds │ error → message
 ├─ stream ended without answer/error → "The connection ended before the answer finished."
 └─ finally: refreshConversations()    Server Action → refresh() → sidebar re-renders (title, order)
```
**To add a new tool to the agent:** add it in `app/agent/tools.py` (doc 14), add a label in `TOOL_LABEL` (`events.ts`), and add a one-line summary case in `summarise_tool_result`. The page needs nothing else.

### 5.4 Developer: running it
```powershell
cd frontend
npm install          # new packages: react-markdown, remark-gfm
npm run dev          # backend on 8010 and Ollama running
```
Open http://localhost:3000/agent. To see streaming in the browser's dev tools: Network → the `/bff/agent/…` request → **EventStream** tab (Chrome) or Response.

---

## 6. Tested

In the sandbox, against the fake backend (FastAPI with a scripted stand-in for Ollama), production build, Chromium:

| Check | Result |
|---|---|
| Types, lint, formatting, `next build` | ✅ (`/agent` ◐ partial prerender, `/agent/[id]` ◐, `/bff/agent/[id]` ƒ) |
| Streaming timing, rewrite vs relay | rewrite: all chunks at 4.2 s (gzip) · relay: one every 0.7 s ✅ |
| New question: URL changes, step with arguments and summary, answer, footer | ✅ (URL at 76 ms) |
| Employee codes become `/employees?q=EMP-…` links | ✅ |
| Follow-up uses the history | ✅ |
| Sidebar shows the new conversation after the answer | ✅ |
| Reload: stored turn identical to the live one (steps, summaries, answer) | ✅ |
| Stop during an answer → "Stopped…" | ✅ |
| Delete with confirmation → back to `/agent` | ✅ |
| Browser console errors | none |

**Not done (the user asked to leave tests for now):** unit tests for `createSseParser` and `messagesToTurns`, a Playwright spec for the chat, and a run with the real model on this PC (action item 17 in doc 07).

---

## 7. Findings

1. **The `/api` rewrite buffers SSE** (gzip). Fixed with the `/bff` Route Handler and `no-transform` (section 2). Only a timed client measurement shows this.
2. **Stored and live steps looked different:** stored tool messages had only raw JSON. The backend now adds the same `summary`, reusing one function.
3. **`EventSource` doesn't fit** a POST with a body and controlled stopping. `fetch` + a stream reader does.
4. **Pre-tool chatter:** small models often write "Let me look that up" before a tool call. Clearing the answer on `tool_call` keeps the final text clean and identical to what's stored.
5. **The proxy must skip `/bff`:** otherwise an expired session gets a 307 to the HTML login page, which `fetch` follows silently and then fails to parse.

---

## 8. Alternatives and enterprise grade

| Topic | Here | Alternatives | Enterprise |
|---|---|---|---|
| Transport | SSE over a POST response | WebSockets (two-way, needs sticky sessions); long polling | SSE through an API gateway with buffering off; WebSockets only for real two-way needs (voice, collaboration) |
| Client | Hand-written `fetch` reader + parser (~60 lines) | Vercel AI SDK `useChat`, `@microsoft/fetch-event-source` | The AI SDK or an in-house SDK shared across apps, with retries and resume |
| Resume after a dropped connection | Not supported: ask again | SSE `id:` + `Last-Event-ID`; a job id plus polling | Agent runs as background jobs (queue); the page subscribes to a run, which survives reloads and deploys |
| Relay | Next.js Route Handler | Browser → FastAPI directly with CORS + a token in JS (worse: token exposed) | API gateway / BFF service with auth, rate limits, audit |
| Rendering model text | `react-markdown`, no raw HTML | `marked` + DOMPurify | The same, plus a strict CSP and link allow-listing |
| Trust | Steps and tool results visible | Citations per sentence | Source citations, feedback buttons (thumbs, "wrong person"), traces in LangSmith/Langfuse/OpenTelemetry |
| Limits | Max 4,000 characters per question; the backend's step limit | Per-user rate limiting | Quotas, cost tracking, prompt-injection filtering on tool results, data-access policies per user |

---

## 9. Limitations

- **No reconnect:** if the connection drops (Wi-Fi, laptop sleep), the turn shows an error and the question must be asked again. FastAPI saves only completed answers.
- **On small screens** the conversation list is hidden to give the chat the full width: **Staffing assistant** in the menu starts a new conversation, and earlier ones are reachable only by their URL or the browser history. A drawer for the list is a small follow-up.
- **One question at a time** per page; the agent itself handles one tool call after another (doc 14).
- **Titles** are the first question, cut to 80 characters; there's no rename.
- **CPU speed:** a real answer takes 30–120 s. The steps make this visible, but not faster. A GPU or a smaller fast model for simple questions would help (doc 06).

---

## 10. Glossary

| Term | Meaning |
|---|---|
| **SSE** | Server-Sent Events: a long-lived HTTP response carrying `data: …` events separated by blank lines |
| **Chunk** | A piece of bytes as the network delivers it; not aligned with events |
| **Relay / BFF** | Server code that forwards a request on the user's behalf (here: adds the token, passes the stream through) |
| **`no-transform`** | A `Cache-Control` directive: intermediaries must not modify (e.g. compress) the body, so streams aren't buffered |
| **AbortController** | Browser API to cancel a `fetch`; here it also stops the agent on the server |
| **Turn** | One question with its steps and answer, the unit the chat shows |
| **Optimistic UI** | Showing the question immediately, before the server has confirmed anything |
