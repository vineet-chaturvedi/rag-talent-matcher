"use client";

import { RotateCw } from "lucide-react";
import { catchError, type ErrorInfo } from "next/error";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

/**
 * An error boundary for ONE part of a page (Next.js 16's `catchError`).
 *
 *   <SectionBoundary title="System health">
 *     <Suspense fallback={<HealthSkeleton />}><HealthCard /></Suspense>
 *   </SectionBoundary>
 *
 * If HealthCard crashes (a bug, not an expected "backend down", which the card shows itself), only
 * this box shows an error with a "Try again" button; the rest of the dashboard keeps working.
 * `retry()` re-renders just this part on the server. Unlike a hand-written React error boundary,
 * catchError lets Next.js's own signals (redirect, notFound) pass through untouched.
 *
 * In production Next.js hides the real error message from the browser (it could contain secrets);
 * the details are in the Next.js server terminal.
 */
function SectionError({ title }: { title: string }, { retry }: ErrorInfo) {
  return (
    <div className="space-y-3 rounded-xl border bg-card p-5">
      <Alert title={`${title} could not be shown`}>
        Something went wrong while loading this part of the page. The details are in the Next.js server log.
      </Alert>
      <Button variant="outline" size="sm" onClick={() => retry()}>
        <RotateCw aria-hidden /> Try again
      </Button>
    </div>
  );
}

export const SectionBoundary = catchError(SectionError);
