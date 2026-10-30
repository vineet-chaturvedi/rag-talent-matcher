import { NextResponse, type NextRequest } from "next/server";

import { AUTH_ROUTES_PREFIX, HOME_PATH, LOGIN_PATH, PUBLIC_PATHS, SESSION_COOKIE } from "@/lib/auth/constants";
import { isTokenExpired } from "@/lib/auth/jwt";

/**
 * Proxy: runs on the Next.js server BEFORE a page renders (Next.js 16's new name for "middleware").
 *
 * An OPTIMISTIC check, as the Next.js docs recommend for proxy: it only reads the cookie and the
 * token's expiry time (fast, no network call), to avoid rendering a portal page for someone who
 * clearly isn't logged in:
 *   - no cookie / expired token, on a portal page -> /login?next=<the page they wanted>
 *   - valid-looking token, on /login              -> the dashboard
 *
 * The SECURE check happens elsewhere: FastAPI verifies the token's signature on every API call, and
 * the session helpers (src/lib/auth/session.ts) redirect if FastAPI says no.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (pathname.startsWith(AUTH_ROUTES_PREFIX)) return NextResponse.next(); // they manage the cookie

  const loggedIn = !isTokenExpired(request.cookies.get(SESSION_COOKIE)?.value);
  const isPublic = (PUBLIC_PATHS as readonly string[]).includes(pathname);

  if (!loggedIn && !isPublic) {
    const url = new URL(LOGIN_PATH, request.url);
    if (pathname !== HOME_PATH) url.searchParams.set("next", pathname + search);
    return NextResponse.redirect(url);
  }
  if (loggedIn && pathname === LOGIN_PATH) {
    return NextResponse.redirect(new URL(HOME_PATH, request.url));
  }
  return NextResponse.next();
}

export const config = {
  // Pages only. Not /api (FastAPI checks those itself), Next.js internals, or files like favicon.ico.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|txt)$).*)"],
};
