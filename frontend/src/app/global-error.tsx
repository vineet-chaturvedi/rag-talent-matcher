"use client";

import "./globals.css";

/**
 * The last line of defence: shown if the ROOT layout itself crashes, so it must render its own
 * <html> and <body> (the normal layout is gone). Keep it dependency-free: anything it imports could
 * be the thing that crashed.
 */
export default function GlobalError({ retry }: { error: unknown; retry: () => void }) {
  return (
    <html lang="en-IN">
      <body className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
        <h1 className="text-xl font-semibold">The portal could not start</h1>
        <p className="max-w-md text-sm text-muted-foreground">
          Something went wrong before any page could load. The details are in the Next.js server log.
        </p>
        <button
          type="button"
          onClick={() => retry()}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          Try again
        </button>
      </body>
    </html>
  );
}
