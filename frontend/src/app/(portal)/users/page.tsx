import type { Metadata } from "next";
import { Suspense } from "react";

import { ComingSoon } from "@/components/coming-soon";
import { PageHeader } from "@/components/layout/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminOnly } from "@/features/auth/components/admin-only";

export const metadata: Metadata = { title: "Users" };

const PLANNED = [
  "Create portal users and choose their role",
  "Reset passwords, change roles, deactivate people who leave",
] as const;

export default function UsersPage() {
  return (
    <>
      <PageHeader title="Users" description="Who can sign in to the portal, and with which role." />
      {/* The role check needs the session, so it streams in; the heading above is instant. */}
      <Suspense fallback={<Skeleton className="h-32 w-full rounded-xl" />}>
        <AdminOnly>
          <ComingSoon step={12} items={PLANNED} />
        </AdminOnly>
      </Suspense>
    </>
  );
}
