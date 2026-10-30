import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";

/** One number tile: a label, a big value, and a small hint underneath. */
export function StatTile({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-xs">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold tabular-nums">{value}</dd>
      {hint && <dd className="mt-0.5 text-xs text-muted-foreground">{hint}</dd>}
    </div>
  );
}

export function StatTileSkeleton() {
  return (
    <div className="space-y-2 rounded-xl border bg-card p-4 shadow-xs">
      <Skeleton className="h-3 w-20" />
      <Skeleton className="h-7 w-14" />
      <Skeleton className="h-3 w-24" />
    </div>
  );
}
