/**
 * Read the expiry time from a JWT WITHOUT verifying it.
 *
 * A JWT is three base64url parts: header.payload.signature. The payload is JSON such as
 *   {"sub": "1", "role": "admin", "exp": 1793370871, "typ": "access"}
 * We only look at "exp" (seconds since 1970) to decide, quickly and optimistically, whether a login
 * is still worth trying. Verifying the signature needs JWT_SECRET, which only FastAPI has; FastAPI
 * checks it on every request, so a forged token gets nowhere.
 *
 * Pure function (no Next.js, no browser APIs except atob, which Node and the Edge runtime have),
 * so it is easy to unit test and safe to run in the proxy.
 */
export function readTokenExpiry(token: string): number | null {
  const payload = token.split(".")[1];
  if (!payload) return null;
  try {
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const data: unknown = JSON.parse(atob(padded));
    if (data && typeof data === "object" && "exp" in data && typeof data.exp === "number") {
      return data.exp * 1000; // -> milliseconds, like Date.now()
    }
    return null;
  } catch {
    return null; // not base64, not JSON: treat as "no usable token"
  }
}

/** True when the token is missing, unreadable, or past its expiry (with a few seconds of slack). */
export function isTokenExpired(token: string | undefined, now: number = Date.now(), skewMs = 5_000): boolean {
  if (!token) return true;
  const expiresAt = readTokenExpiry(token);
  return expiresAt === null || expiresAt - skewMs <= now;
}
