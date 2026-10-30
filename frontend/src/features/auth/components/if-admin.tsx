import type { ReactNode } from "react";

import { getCurrentUser, isAdmin } from "@/lib/auth/session";

/**
 * Show a PART of a page (an upload box, a delete button) only to admins, and nothing to others.
 * Like AdminOnly, this is about a clear page, not security: FastAPI refuses admin actions with 403.
 * Async (reads the session), so place it inside a <Suspense> boundary.
 */
export async function IfAdmin({ children }: { children: ReactNode }) {
  const user = await getCurrentUser();
  return isAdmin(user) ? <>{children}</> : null;
}
