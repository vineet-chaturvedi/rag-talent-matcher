import { HOME_PATH, LOGIN_PATH } from "./constants";

/**
 * Turn the `next` value from the login URL (/login?next=/projects) into a SAFE place to go.
 *
 * Why: `next` comes from the URL, so anyone can craft a link like
 *   https://portal/login?next=https://evil.example/fake-login
 * If we redirected there after a real login, the user would trust the fake page ("open redirect").
 * So only same-site paths are accepted:
 *   "/projects?id=3"       -> allowed
 *   "https://evil.example" -> "/"   (absolute URL)
 *   "//evil.example"       -> "/"   (protocol-relative URL: the browser treats it as another site)
 *   "/\evil.example"       -> "/"   (some browsers turn "\" into "/")
 *   "/login"               -> "/"   (would loop back to the login page)
 */
export function safeNextPath(value: unknown): string {
  if (typeof value !== "string" || value.length === 0 || value.length > 2048) return HOME_PATH;
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return HOME_PATH;
  if (/[\u0000-\u001f]/.test(value)) return HOME_PATH; // control characters (e.g. a tab or newline)
  const pathname = value.split(/[?#]/)[0] ?? value;
  if (pathname === LOGIN_PATH || pathname.startsWith("/auth/")) return HOME_PATH;
  return value;
}
