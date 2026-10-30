import type { ReactNode } from "react";

import { Alert } from "@/components/ui/alert";
import { getCurrentUser, isAdmin } from "@/lib/auth/session";

/**
 * Render `children` only for administrators; everyone else sees a short explanation.
 *
 * This is for a clear page, NOT the security boundary: the admin-only FastAPI endpoints answer 403 to
 * anyone else, whatever the page shows, and every Server Action re-checks on its own.
 */
export async function AdminOnly({ children }: { children: ReactNode }) {
  const user = await getCurrentUser();
  if (!isAdmin(user)) {
    return (
      <Alert tone="warning" title="Administrators only">
        This page manages portal accounts. Ask an administrator if you need access.
      </Alert>
    );
  }
  return <>{children}</>;
}
