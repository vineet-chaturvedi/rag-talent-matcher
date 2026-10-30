import "server-only";

import { cookies } from "next/headers";

import { request } from "@/lib/api/client";
import type { UserRole } from "@/lib/api/types";
import { env } from "@/lib/env";

import { SESSION_COOKIE } from "./constants";

/**
 * The session, on the server (part of the Data Access Layer).
 *
 * The session IS the HttpOnly cookie holding FastAPI's JWT. Next.js never verifies the token itself
 * (it doesn't have JWT_SECRET); it forwards it, and FastAPI decides. One source of truth for "who is
 * this and what may they do": the backend (Step 9).
 */

/** Only what the UI needs about the signed-in person (a "DTO"): no token, no timestamps. */
export type SessionUser = {
  id: number;
  email: string;
  fullName: string;
  role: UserRole;
};

/**
 * Who is signed in? Asks FastAPI (GET /api/auth/me) with the cookie's token.
 *
 * `"use cache: private"` (Next.js 16): the result may be reused within this request (the shell's user
 * menu, the navigation and the page all ask, but FastAPI is called once) and kept in the browser's
 * router cache for a few minutes, so moving between pages doesn't refetch it. It is never stored in a
 * server-side cache shared between users. That is what the Next.js "Authentication with Cache
 * Components" guide recommends for reading a session.
 *
 * - Session invalid (401)  -> request() ends the session and redirects to /login.
 * - Backend down / error   -> throws, so the nearest error boundary shows a problem. Errors are never
 *                             cached, so the next navigation tries again.
 */
export async function getCurrentUser(): Promise<SessionUser> {
  "use cache: private";
  const result = await request((api) => api.GET("/api/auth/me"));
  if (!result.ok) throw new Error(`Could not load your account: ${result.message}`);
  const { id, email, full_name, role } = result.data;
  return { id, email, fullName: full_name, role };
}

export function isAdmin(user: SessionUser): boolean {
  return user.role === "admin";
}

/** Store a new login. Only callable where cookies may change: Server Actions and Route Handlers. */
export async function setSessionCookie(token: string, expiresAt: string): Promise<void> {
  (await cookies()).set(SESSION_COOKIE, token, {
    httpOnly: true, // page JavaScript can't read it
    sameSite: "lax", // not sent with cross-site POSTs (CSRF protection)
    secure: env.HTTPS, // HTTPS-only when the portal runs on HTTPS
    path: "/",
    expires: new Date(expiresAt), // the browser forgets it when the JWT expires
  });
}

export async function clearSessionCookie(): Promise<void> {
  (await cookies()).delete(SESSION_COOKIE);
}
