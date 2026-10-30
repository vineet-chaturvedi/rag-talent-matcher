/**
 * Auth constants shared by the proxy, the session helpers and the Server Actions.
 *
 * SESSION_COOKIE must equal the backend's AUTH_COOKIE_NAME (default "rtm_access"): the browser sends
 * this cookie to /api/... too, and FastAPI reads it when a Client Component calls the API through the
 * rewrite (the agent's live stream in Step 13).
 */
export const SESSION_COOKIE = "rtm_access";

/** Pages anyone may open without being logged in. Everything else needs a session. */
export const PUBLIC_PATHS = ["/login"] as const;

/** Route handlers under /auth/ manage the cookie themselves, so the proxy lets them through. */
export const AUTH_ROUTES_PREFIX = "/auth/";

export const LOGIN_PATH = "/login";
export const HOME_PATH = "/";
