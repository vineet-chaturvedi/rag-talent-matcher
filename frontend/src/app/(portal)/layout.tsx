import { Suspense } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { AccountSlot, AccountSlotFallback, RoleNav, RoleNavFallback } from "@/features/auth/components/session-parts";

/**
 * Layout for every signed-in page. "(portal)" in brackets is a ROUTE GROUP: it groups pages under one
 * layout without adding "/portal" to the URL.
 *
 * Rule from the Next.js docs: never `await` the session at the top of a layout, or every page below
 * waits for it. Here the frame renders immediately; only the two user-specific parts (menu items
 * that depend on the role, the account menu) wait, each behind its own <Suspense>.
 * proxy.ts has already sent visitors without a login cookie to /login.
 */
export default function PortalLayout({ children }: LayoutProps<"/">) {
  return (
    <AppShell
      nav={
        <Suspense fallback={<RoleNavFallback />}>
          <RoleNav />
        </Suspense>
      }
      account={
        <Suspense fallback={<AccountSlotFallback />}>
          <AccountSlot />
        </Suspense>
      }
    >
      {children}
    </AppShell>
  );
}
