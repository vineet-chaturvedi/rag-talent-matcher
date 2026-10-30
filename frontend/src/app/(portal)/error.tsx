"use client";

import { RotateCw } from "lucide-react";
import { useEffect } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

/**
 * Shown instead of a portal page that crashed while rendering; the sidebar stays usable.
 *
 * Next.js 16 passes `error` (typed `unknown`: anything can be thrown) and `retry()`, which re-fetches
 * and re-renders this segment on the server. (Older versions passed `reset()`, which only re-rendered
 * on the client and so couldn't recover from a server error.)
 * In production `error.message` is replaced by a generic text plus a `digest` ID; the real message is
 * in the Next.js server log next to that ID, so secrets never reach the browser.
 */
export default function PortalError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error); // the place to report to an error tracker (Sentry, OpenTelemetry) later
  }, [error]);

  const digest = error && typeof error === "object" && "digest" in error ? String(error.digest) : null;

  return (
    <div className="space-y-4">
      <Alert title="This page could not be shown">
        Something went wrong while loading it. Check that the backend is running, then try again.
        {digest && <span className="mt-1 block text-xs">Reference: {digest}</span>}
      </Alert>
      <Button variant="outline" onClick={() => retry()}>
        <RotateCw aria-hidden /> Try again
      </Button>
    </div>
  );
}
