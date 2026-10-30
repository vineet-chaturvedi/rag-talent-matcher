import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ChangePasswordForm } from "@/features/users/components/change-password-form";
import { ROLE_LABEL } from "@/features/users/schemas";
import { getCurrentUser } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Account" };

/** Your own account: who you are signed in as, and changing your password. For every signed-in user. */
export default function AccountPage() {
  return (
    <>
      <PageHeader title="Account" description="Your sign-in details." />
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Signed in as</CardTitle>
          </CardHeader>
          <CardContent>
            <Suspense fallback={<Skeleton className="h-12 w-64" />}>
              <Me />
            </Suspense>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Change password</CardTitle>
          </CardHeader>
          <CardContent>
            <ChangePasswordForm />
          </CardContent>
        </Card>
      </div>
    </>
  );
}

async function Me() {
  const user = await getCurrentUser();
  return (
    <dl className="grid gap-3 text-sm sm:grid-cols-3">
      <div>
        <dt className="text-xs text-muted-foreground">Name</dt>
        <dd>{user.fullName}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Email</dt>
        <dd>{user.email}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Role</dt>
        <dd>{ROLE_LABEL[user.role]}</dd>
      </div>
    </dl>
  );
}
