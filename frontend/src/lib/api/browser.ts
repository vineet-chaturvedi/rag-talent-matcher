import createClient from "openapi-fetch";

import { messageFromDetail } from "./errors";
import type { paths } from "./schema";

/**
 * The typed FastAPI client for BROWSER code, used only where the browser must send something big
 * itself: file uploads (resumes, the HR CSV), and in Step 13 the agent's live stream.
 *
 * Why not a Server Action for uploads: an action's request body is limited (1 MB by default) and
 * would pass every file through the Next.js server's memory. Instead the browser POSTs straight to
 * /api/..., which the rewrite in next.config.ts forwards to FastAPI as a stream. The HttpOnly cookie
 * goes along automatically (same site), so the token is still never readable by page JavaScript.
 */
export const browserApi = createClient<paths>({ baseUrl: "" });

/** A readable message from a failed call; a 401 sends the person to the login page. */
export function browserErrorMessage(error: unknown, response: Response): string {
  if (response.status === 401) {
    // A full page load on purpose: /auth/session-expired is a Route Handler that deletes the cookie,
    // which a client-side router.push() can't run (it fetches page data, not a handler's redirect).
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/auth/session-expired");
  }
  return messageFromDetail(error, response.status);
}
