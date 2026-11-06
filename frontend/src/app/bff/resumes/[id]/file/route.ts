import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/auth/constants";
import { env } from "@/lib/env";
import { idParam } from "@/lib/search-params";

/**
 * GET /bff/resumes/{resumeId}/file: the ORIGINAL uploaded resume (any version), for admins.
 *   ?download=1  save it instead of opening it (PDFs open in the browser's viewer by default;
 *                Word files are always downloaded, since browsers can't display them).
 *
 * A Route Handler relay, like /bff/agent: the login token is read from the HttpOnly cookie here on the
 * server and sent to FastAPI as a Bearer token; browser code never touches it. The file is streamed
 * through without being held in memory. FastAPI decides who may see it (admins only, 403 otherwise).
 *
 * The browser navigates here directly (a link in a new tab), so errors come back as a short readable
 * page rather than JSON, and an expired session goes to the login page.
 */
const PASS_THROUGH = ["content-type", "content-length", "content-disposition"] as const;

export async function GET(request: NextRequest, context: RouteContext<"/bff/resumes/[id]/file">) {
  const resumeId = idParam((await context.params).id);
  if (resumeId === null) return message(404, "This resume does not exist.");

  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return NextResponse.redirect(new URL("/login", request.url));

  const download = request.nextUrl.searchParams.get("download") === "1";
  let upstream: Response;
  try {
    upstream = await fetch(`${env.BACKEND_URL}/api/resumes/${resumeId}/file${download ? "?download=true" : ""}`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: request.signal,
      cache: "no-store",
    });
  } catch {
    return message(502, "Cannot reach the backend. Is FastAPI running (uvicorn on port 8010)?");
  }

  if (upstream.status === 401) return NextResponse.redirect(new URL("/auth/session-expired", request.url));
  if (!upstream.ok || !upstream.body) {
    const body = (await upstream.json().catch(() => null)) as { detail?: unknown } | null;
    const detail =
      typeof body?.detail === "string"
        ? body.detail
        : upstream.status === 403
          ? "Only admins can open original resumes."
          : `The file could not be loaded (HTTP ${upstream.status}).`;
    return message(upstream.status, detail);
  }

  const headers = new Headers({
    "Cache-Control": "private, no-store, no-transform", // personal data: never cached; bytes untouched
    "X-Content-Type-Options": "nosniff",
  });
  for (const name of PASS_THROUGH) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new Response(upstream.body, { headers });
}

function message(status: number, text: string): Response {
  return new Response(text, { status, headers: { "Content-Type": "text/plain; charset=utf-8" } });
}
