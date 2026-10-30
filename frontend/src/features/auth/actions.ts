"use server";

import type { Route } from "next";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { z } from "zod";

import { request } from "@/lib/api/client";
import { LOGIN_PATH } from "@/lib/auth/constants";
import { safeNextPath } from "@/lib/auth/redirect";
import { clearSessionCookie, setSessionCookie } from "@/lib/auth/session";

import { loginSchema, type LoginState } from "./schemas";

/**
 * Server Actions for signing in and out.
 *
 * A Server Action is a function that runs on the Next.js server but can be used as a <form action>.
 * The browser POSTs the form to this server; no fetch code, no JSON, and the form even works before
 * the page's JavaScript has loaded ("progressive enhancement"). Next.js also checks that the POST
 * came from this site (Origin header must match Host), which blocks cross-site form attacks.
 *
 * Every exported function here is a public endpoint: treat its input as untrusted, validate it.
 */

export async function login(_previous: LoginState, formData: FormData): Promise<LoginState> {
  const parsed = loginSchema.safeParse({ email: formData.get("email"), password: formData.get("password") });
  const typedEmail = typeof formData.get("email") === "string" ? String(formData.get("email")) : "";
  if (!parsed.success) {
    return { fieldErrors: z.flattenError(parsed.error).fieldErrors, email: typedEmail };
  }

  // Server-to-server: Next.js -> FastAPI. 401 here means "wrong password", not "session ended".
  const result = await request((api) => api.POST("/api/auth/login", { body: parsed.data }), { on401: "return" });
  if (!result.ok) {
    return { message: result.message, email: parsed.data.email };
  }

  await setSessionCookie(result.data.access_token, result.data.expires_at);
  // redirect() works by throwing, so it must stay outside any try/catch.
  redirect(safeNextPath(await nextFromReferer()) as Route);
}

/**
 * Where to go after logging in: the ?next= of the login page the form was posted from.
 * Read from the Referer header (the page's own URL, sent by the browser with the POST) instead of a
 * hidden field, so the form needs no request data and can be part of the static page: then it works
 * even before or without JavaScript. safeNextPath() still validates it, because headers can be forged.
 */
async function nextFromReferer(): Promise<string | null> {
  const referer = (await headers()).get("referer");
  if (!referer) return null;
  try {
    return new URL(referer).searchParams.get("next");
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
  // Tell the backend (stateless JWTs today; a token blocklist later would need this call).
  // The result doesn't matter: the cookie is deleted either way.
  await request((api) => api.POST("/api/auth/logout"), { on401: "return" });
  await clearSessionCookie();
  redirect(LOGIN_PATH);
}
