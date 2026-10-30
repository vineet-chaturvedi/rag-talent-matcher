import { Sparkles } from "lucide-react";
import type { Metadata } from "next";
import { Suspense } from "react";

import { Alert } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { login } from "@/features/auth/actions";
import { LoginForm } from "@/features/auth/components/login-form";

export const metadata: Metadata = { title: "Sign in" };

/**
 * The login page: entirely static, so it appears instantly AND the form works without JavaScript
 * (streamed content is revealed by a script, so a form inside <Suspense> would stay hidden).
 * Only the "your session has ended" notice depends on the URL (?expired=1), so only it is in
 * <Suspense>. Where to go after login (?next=) is read by the Server Action itself.
 */
export default function LoginPage(props: PageProps<"/login">) {
  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-2 text-center">
          <span className="mx-auto flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Sparkles className="size-5" aria-hidden />
          </span>
          <h1 className="text-xl font-semibold tracking-tight">Talent Matcher</h1>
          <p className="text-sm text-muted-foreground">Sign in to the internal staffing portal</p>
        </div>
        <Card>
          <CardContent>
            <LoginForm
              action={login}
              notice={
                <Suspense>
                  <ExpiredNotice searchParams={props.searchParams} />
                </Suspense>
              }
            />
          </CardContent>
        </Card>
        <p className="text-center text-xs text-muted-foreground">
          No account? Ask an administrator: accounts are created by admins.
        </p>
      </div>
    </main>
  );
}

async function ExpiredNotice({ searchParams }: Pick<PageProps<"/login">, "searchParams">) {
  const { expired } = await searchParams;
  if (expired !== "1") return null;
  return <Alert tone="info">Your session has ended. Please log in again.</Alert>;
}
