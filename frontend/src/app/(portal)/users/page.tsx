import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { SectionBoundary } from "@/components/section-boundary";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminOnly } from "@/features/auth/components/admin-only";
import { NewUserForm } from "@/features/users/components/new-user-form";
import { UsersTable, UsersTableSkeleton } from "@/features/users/components/users-table";

export const metadata: Metadata = { title: "Users" };

/** Portal accounts (admins): who can sign in, with which role. Accounts are deactivated, never deleted. */
export default function UsersPage() {
  return (
    <>
      <PageHeader title="Users" description="Who can sign in to the portal, and with which role." />
      {/* The role check needs the session, so it streams in; the heading above is instant. */}
      <Suspense fallback={<Skeleton className="h-48 w-full rounded-xl" />}>
        <AdminOnly>
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Accounts</CardTitle>
              </CardHeader>
              <CardContent>
                <SectionBoundary title="The account list">
                  <Suspense fallback={<UsersTableSkeleton />}>
                    <UsersTable />
                  </Suspense>
                </SectionBoundary>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <div className="space-y-1">
                  <CardTitle>New account</CardTitle>
                  <CardDescription>
                    For colleagues who staff projects (resource managers) or run the portal (admins).
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <NewUserForm />
              </CardContent>
            </Card>
          </div>
        </AdminOnly>
      </Suspense>
    </>
  );
}
