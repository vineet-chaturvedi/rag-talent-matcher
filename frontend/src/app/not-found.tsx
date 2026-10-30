import Link from "next/link";

import { Button } from "@/components/ui/button";

/** Any URL that matches no page. Static: no data, renders instantly. */
export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
      <div className="space-y-1">
        <p className="text-sm font-medium text-muted-foreground">404</p>
        <h1 className="text-xl font-semibold tracking-tight">Page not found</h1>
      </div>
      <Button asChild variant="outline">
        <Link href="/">Back to the dashboard</Link>
      </Button>
    </main>
  );
}
