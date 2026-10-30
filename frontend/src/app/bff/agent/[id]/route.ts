import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { z } from "zod";

import { SESSION_COOKIE } from "@/lib/auth/constants";
import { env } from "@/lib/env";
import { idParam } from "@/lib/search-params";

/**
 * POST /bff/agent/{conversationId}: ask the staffing agent; the answer streams back as Server-Sent
 * Events (Step 13).
 *
 * A Route Handler as a streaming relay ("backend for frontend"):
 *   browser ──POST question──▶ this handler ──Bearer token──▶ FastAPI /api/agent/.../messages
 *   browser ◀──SSE events──── this handler ◀──SSE events──── FastAPI (tool calls, tokens, answer)
 *
 * Why not the /api rewrite: here, like everywhere else, the token is read from the HttpOnly cookie
 * on the SERVER and never handled by browser code; the question is validated before FastAPI sees it;
 * and if the person presses Stop or leaves the page, `request.signal` aborts the upstream request,
 * so FastAPI stops the agent instead of finishing an answer nobody reads.
 *
 * Why "no-transform": Next.js gzips responses, and a compressor buffers its input, which would hold
 * back the stream until the end. `Cache-Control: no-transform` tells the compression layer (and any
 * proxy in between) to pass the bytes through untouched, so each token arrives when it is produced.
 */
const askSchema = z.object({ content: z.string().trim().min(1).max(4000) });

export async function POST(request: NextRequest, context: RouteContext<"/bff/agent/[id]">) {
  const conversationId = idParam((await context.params).id);
  if (conversationId === null) return Response.json({ detail: "Unknown conversation." }, { status: 404 });

  const parsed = askSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return Response.json({ detail: "Write a question (up to 4,000 characters)." }, { status: 422 });

  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return Response.json({ detail: "Your session has ended. Please log in again." }, { status: 401 });

  let upstream: Response;
  try {
    upstream = await fetch(`${env.BACKEND_URL}/api/agent/conversations/${conversationId}/messages`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ content: parsed.data.content, stream: true }),
      signal: request.signal, // the browser went away -> stop asking FastAPI
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { detail: "Cannot reach the backend. Is FastAPI running (uvicorn on port 8010)?" },
      { status: 502 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    // Pass FastAPI's error (404 not your conversation, 401 session, 503 Ollama...) through as JSON.
    const detail = await upstream.json().catch(() => ({ detail: `The agent failed (HTTP ${upstream.status}).` }));
    return Response.json(detail, { status: upstream.status });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no", // nginx and similar proxies: don't buffer
    },
  });
}
