import { Sparkles } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

/**
 * The frame around every signed-in page: sidebar (desktop) or top bar (mobile), and the content area.
 *
 * A Server Component with NO data of its own: it receives the parts that need the session (`nav`,
 * `account`) as slots, already wrapped in <Suspense> by the layout. So the frame itself is static:
 * it is prerendered into the static shell and appears instantly, and the user-specific parts stream
 * in a moment later.
 */
export function AppShell({ nav, account, children }: { nav: ReactNode; account: ReactNode; children: ReactNode }) {
  return (
    <div className="min-h-dvh md:grid md:grid-cols-[15rem_1fr]">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-card px-3 py-2 text-sm shadow focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>

      <aside className="border-b bg-card md:sticky md:top-0 md:flex md:h-dvh md:flex-col md:border-r md:border-b-0">
        <div className="flex items-center justify-between gap-3 px-4 py-3 md:py-5">
          <Link href="/" className="flex items-center gap-2 text-sm font-semibold">
            <span className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Sparkles className="size-4" aria-hidden />
            </span>
            Talent Matcher
          </Link>
          <div className="md:hidden">{account}</div>
        </div>
        <nav aria-label="Main" className="px-3 pb-3 md:flex-1">
          {nav}
        </nav>
        <div className="hidden border-t p-3 md:block">{account}</div>
      </aside>

      <main id="main" className="mx-auto w-full max-w-6xl min-w-0 px-4 py-6 md:px-8 md:py-8">
        {children}
      </main>
    </div>
  );
}
