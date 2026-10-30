import { AutoRefresh } from "@/components/auto-refresh";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn, formatNumber } from "@/lib/utils";

import { IN_PROGRESS, PIPELINE_STAGES } from "@/features/resumes/labels";
import { getQueueStats } from "@/features/resumes/queries";

/** Where every current resume is in the pipeline (upload -> text -> AI profile -> searchable). */
export async function PipelineCard() {
  const stats = await getQueueStats();
  if (!stats.ok) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Resume pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          <Alert>{stats.message}</Alert>
        </CardContent>
      </Card>
    );
  }

  const { by_status, total, worker_running } = stats.data;
  const busy = IN_PROGRESS.some((status) => (by_status[status] ?? 0) > 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Resume pipeline</CardTitle>
        <CardAction>
          <Badge tone={worker_running ? "success" : "warning"}>
            {worker_running ? "worker running" : "worker stopped"}
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent>
        {/* Live while there is work: re-render every 10 s. Nothing to process -> no polling. */}
        {busy && <AutoRefresh seconds={10} />}
        <ul className="space-y-2.5">
          {PIPELINE_STAGES.map(({ status, label }) => {
            const count = by_status[status] ?? 0;
            const share = total ? (count / total) * 100 : 0;
            return (
              <li key={status} className="grid grid-cols-[7rem_1fr_2.5rem] items-center gap-3 text-sm">
                <span className="text-muted-foreground">{label}</span>
                <span
                  className="h-2 overflow-hidden rounded-full bg-muted"
                  role="meter"
                  aria-label={label}
                  aria-valuemin={0}
                  aria-valuemax={total}
                  aria-valuenow={count}
                >
                  <span
                    className={cn(
                      "block h-full rounded-full",
                      status === "failed" ? "bg-destructive" : status === "ready" ? "bg-success" : "bg-primary",
                    )}
                    style={{ width: `${share}%` }}
                  />
                </span>
                <span className="text-right tabular-nums">{formatNumber(count)}</span>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}

export function PipelineCardSkeleton() {
  return (
    <Card role="status" aria-label="Loading the resume pipeline">
      <CardHeader>
        <CardTitle>Resume pipeline</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {PIPELINE_STAGES.map(({ status }) => (
          <Skeleton key={status} className="h-4 w-full" />
        ))}
      </CardContent>
    </Card>
  );
}
