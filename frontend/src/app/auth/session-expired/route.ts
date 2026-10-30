import { NextResponse, type NextRequest } from "next/server";

import { clearSessionCookie } from "@/lib/auth/session";

/**
 * GET /auth/session-expired: FastAPI rejected the login token (it expired, the account was
 * deactivated, or JWT_SECRET changed). Delete the cookie, then go to the login page with a notice.
 *
 * Why a Route Handler: pages (Server Components) are not allowed to change cookies, and if the old
 * cookie stayed, the proxy would still think "logged in" and send /login straight back to the
 * dashboard: an endless loop. Route Handlers may change cookies, so the API client redirects here.
 */
export async function GET(request: NextRequest) {
  await clearSessionCookie();
  return NextResponse.redirect(new URL("/login?expired=1", request.url));
}
