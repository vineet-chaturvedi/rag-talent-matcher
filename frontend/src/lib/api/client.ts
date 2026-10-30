import "server-only";

import { cookies } from "next/headers";
import { redirect, unstable_rethrow } from "next/navigation";
import createClient, { type Client } from "openapi-fetch";

import { SESSION_COOKIE } from "@/lib/auth/constants";
import { env } from "@/lib/env";

import { type ApiResult, fallbackMessage, messageFromDetail } from "./errors";
import type { paths } from "./schema";

/**
 * The ONE way server code talks to FastAPI: a typed client generated from FastAPI's OpenAPI document.
 *
 *   const result = await request((api) => api.GET("/api/overview"));
 *   if (result.ok) result.data.employees.total   // <- TypeScript knows this shape
 *
 * - `paths` (schema.d.ts) is GENERATED from http://127.0.0.1:8010/openapi.json by `npm run api:types`.
 *   Rename a field in a Pydantic model, regenerate, and every page using it stops compiling.
 * - The call happens server-to-server (Next.js -> FastAPI). The browser never sees the backend.
 * - The login token travels in the Authorization header, read from the HttpOnly cookie on this
 *   server. Page JavaScript can't read that cookie, so an XSS bug can't steal the token.
 * - `import "server-only"`: importing this file from a Client Component fails the build.
 */
export type BackendClient = Client<paths>;

type FetchResult<T> = { data?: T; error?: unknown; response: Response };

type RequestOptions = {
  /**
   * What a 401 means. For normal calls it means "the session is no longer valid" (expired, the
   * account was deactivated, or the backend's JWT_SECRET changed), so we end the session and go to
   * the login page. For the login call itself, 401 just means "wrong password": return it.
   */
  on401?: "end-session" | "return";
};

/**
 * Run one backend call and turn every outcome into an ApiResult:
 *   2xx                  -> { ok: true, data }
 *   401                  -> end the session (redirect), unless on401 = "return"
 *   other 4xx / 5xx      -> { ok: false, status, message }   (FastAPI's "detail" when it sent one)
 *   backend not running  -> { ok: false, status: 0, message }
 *
 * Why return instead of throw: "the backend is down" or "not found" are EXPECTED situations that a
 * page should show calmly in place. Thrown errors are for bugs; they go to error boundaries, and in
 * production Next.js hides their message.
 *
 * Why the client is created per call, after reading the cookie: reading cookies() FIRST tells
 * Next.js "this is request-time work" before anything else happens. (Found the hard way: a shared
 * client with an auth middleware made openapi-fetch call Math.random() for a request ID before the
 * cookie was read, and the build stopped with "unstable value Math.random() while prerendering".)
 * Creating the client is just an object with a few functions: negligible next to an HTTP call.
 */
export async function request<T>(
  call: (api: BackendClient) => Promise<FetchResult<T>>,
  { on401 = "end-session" }: RequestOptions = {},
): Promise<ApiResult<T>> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  const api = createClient<paths>({
    baseUrl: env.BACKEND_URL,
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });

  let result: FetchResult<T>;
  try {
    result = await call(api);
  } catch (cause) {
    unstable_rethrow(cause); // never swallow Next.js's own control-flow signals (redirect, prerender)
    console.error("[api] backend unreachable:", cause);
    return { ok: false, status: 0, message: fallbackMessage(0) };
  }

  const { data, error, response } = result;
  if (response.ok) return { ok: true, data: data as T };
  if (response.status === 401 && on401 === "end-session") {
    // A Server Component may not change cookies, so a Route Handler deletes it and redirects to /login.
    redirect("/auth/session-expired");
  }
  return { ok: false, status: response.status, message: messageFromDetail(error, response.status) };
}
