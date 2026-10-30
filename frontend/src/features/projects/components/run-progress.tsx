import { AutoRefresh } from "@/components/auto-refresh";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import type { MatchRun } from "@/lib/api/types";
import { formatDateTime } from "@/lib/utils";

import { RUN_STATUS } from "../labels";

/**
 * The run's state. While the judge is still working (status "running"), the page re-renders every
 * 5 seconds, so each verdict appears as soon as it is saved, and the order updates at the end
 * (the judged top N are re-ranked by their final score once all are done).
 */
export function RunProgress({ run }: { run: MatchRun }) {
  const running = run.status === "running";
  const percent = run.to_judge ? Math.round((run.judged / run.to_judge) * 100) : 100;
  return (
    <div className="space-y-3">
      {running && <AutoRefresh seconds={5} />}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge tone={RUN_STATUS[run.status].tone}>{RUN_STATUS[run.status].label}</Badge>
        <span className="text-muted-foreground">
          started {formatDateTime(run.started_at)}
          {run.finished_at && ` · finished ${formatDateTime(run.finished_at)}`}
        </span>
      </div>
      {run.to_judge > 0 && (
        <div className="space-y-1">
          <div
            className="h-2 overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-label="Judge progress"
            aria-valuemin={0}
            aria-valuemax={run.to_judge}
            aria-valuenow={run.judged}
          >
            <div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${percent}%` }} />
          </div>
          <p className="text-xs text-muted-foreground">
            The AI judge has read {run.judged} of {run.to_judge} resumes
            {running && " (about a minute each); this page updates by itself"}.
          </p>
        </div>
      )}
      {run.status === "failed" && <Alert title="The run stopped">{run.error_message ?? "Unknown error."}</Alert>}
    </div>
  );
}
