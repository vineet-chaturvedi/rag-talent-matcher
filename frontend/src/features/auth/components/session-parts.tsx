import { NavLinks, NavLinksStatic } from "@/components/layout/nav-links";
import { navItemsFor } from "@/components/layout/navigation";
import { Skeleton } from "@/components/ui/skeleton";
import { getCurrentUser } from "@/lib/auth/session";

import { AccountMenu } from "./account-menu";

/**
 * The parts of the shell that depend on WHO is signed in. Each is an async Server Component, so it
 * must sit inside <Suspense>; the layout shows the matching fallback below while it loads.
 * getCurrentUser() is called by both, but FastAPI is asked once ("use cache: private").
 */

export async function RoleNav() {
  const user = await getCurrentUser();
  return <NavLinks items={navItemsFor(user.role)} />;
}

/** While the role is unknown, show the links everyone has: no layout jump for most users. */
export function RoleNavFallback() {
  return <NavLinksStatic items={navItemsFor(null)} />;
}

export async function AccountSlot() {
  const user = await getCurrentUser();
  return <AccountMenu user={user} />;
}

export function AccountSlotFallback() {
  return (
    <div className="flex items-center gap-2.5 p-1.5" role="status" aria-label="Loading your account">
      <Skeleton className="size-8 rounded-full" />
      <div className="hidden flex-1 space-y-1.5 md:block">
        <Skeleton className="h-3.5 w-28" />
        <Skeleton className="h-3 w-20" />
      </div>
    </div>
  );
}
