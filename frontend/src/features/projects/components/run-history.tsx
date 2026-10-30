import { History } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/utils";

import { RUN_STATUS } from "../labels";
import { listMatchRuns } from "../queries";

/**
 * Every match run for this role, newest first. Runs are never overwritten: each keeps the
 * requirements, settings and results it was made with, so a decision can be explained later.
 */
export async function RunHistory({ roleId }: { roleId: number }) {
  const result = await listMatchRuns(roleId);
  if (!result.ok) return <Alert>{result.message}</Alert>;
  if (result.data.length === 0) {
    return (
      <EmptyState icon={History} title="No match runs yet">
        Start one above: the ranking appears in about a second.
      </EmptyState>
    );
  }
  return (
    <ul className="-mx-3 divide-y">
      {result.data.map((run) => (
        <li key={run.id}>
          <Link
            href={`/match-runs/${run.id}` as Route}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg px-3 py-2.5 hover:bg-muted"
          >
            <span className="text-sm font-medium">Run #{run.id}</span>
            <Badge tone={RUN_STATUS[run.status].tone}>{RUN_STATUS[run.status].label}</Badge>
            <span className="text-xs text-muted-foreground">
              {formatDateTime(run.started_at)} · {run.result_count} ranked
              {run.judge_top_n ? ` · judge read ${run.judge_top_n}` : " · rules only"}
            </span>
            {run.top_names.length > 0 && (
              <span className="w-full text-xs text-muted-foreground">Top: {run.top_names.join(", ")}</span>
            )}
          </Link>
        </li>
      ))}
    </ul>
  );
}
