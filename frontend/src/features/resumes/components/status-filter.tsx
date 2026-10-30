import type { Route } from "next";
import Link from "next/link";

import type { QueueStats, ResumeStatus } from "@/lib/api/types";
import { cn, formatNumber } from "@/lib/utils";

import { PIPELINE_STAGES } from "../labels";

/**
 * "All · Queued 2 · … · Failed 1" filter links. Links (not buttons with state): the filter is in the
 * URL, so it survives a reload and can be shared ("look at /resumes?status=failed").
 */
export function StatusFilter({ stats, active }: { stats: QueueStats | null; active?: ResumeStatus }) {
  const items: { label: string; href: Route; count?: number; status?: ResumeStatus }[] = [
    { label: "All", href: "/resumes", count: stats?.total },
    ...PIPELINE_STAGES.map(({ status, label }) => ({
      label,
      status,
      href: `/resumes?status=${status}` as Route,
      count: stats?.by_status[status],
    })),
  ];
  return (
    <nav aria-label="Filter by status" className="flex flex-wrap gap-1.5">
      {items.map((item) => {
        const current = item.status === active;
        return (
          <Link
            key={item.label}
            href={item.href}
            aria-current={current ? "page" : undefined}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
              current ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-muted",
            )}
          >
            {item.label}
            {item.count !== undefined && <span className="tabular-nums opacity-75">{formatNumber(item.count)}</span>}
          </Link>
        );
      })}
    </nav>
  );
}
