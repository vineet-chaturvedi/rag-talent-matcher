import { ArrowLeft, UserSearch } from "lucide-react";
import type { Metadata, Route } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { EmptyState } from "@/components/empty-state";
import { SectionBoundary } from "@/components/section-boundary";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ResultCard } from "@/features/projects/components/result-card";
import { RunProgress } from "@/features/projects/components/run-progress";
import { getMatchRun } from "@/features/projects/queries";
import { idParam } from "@/lib/search-params";

export const metadata: Metadata = { title: "Match results" };

/**
 * One match run: the ranked people for a role, each with the evidence behind their place.
 * Everything comes from what the run stored, so the page shows exactly what was decided at the time,
 * even if the role's requirements or a resume changed since.
 */
export default function MatchRunPage(props: PageProps<"/match-runs/[id]">) {
  return (
    <SectionBoundary title="This match run">
      <Suspense fallback={<RunSkeleton />}>
        <Run params={props.params} />
      </Suspense>
    </SectionBoundary>
  );
}

async function Run({ params }: Pick<PageProps<"/match-runs/[id]">, "params">) {
  const id = idParam((await params).id);
  if (id === null) notFound();
  const result = await getMatchRun(id);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <Alert>{result.message}</Alert>;
  }
  const run = result.data;
  const requirements = run.settings?.requirements;
  const judgeWeight = run.settings?.judge_weight ?? 0.4;

  return (
    <>
      <Link
        href={`/roles/${run.role_id}` as Route}
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden /> {run.role_title}
      </Link>
      <header className="mb-6 space-y-3">
        <h1 className="text-xl font-semibold tracking-tight">
          Best matches for {run.role_title} <span className="text-muted-foreground">· run #{run.id}</span>
        </h1>
        <RunProgress run={run} />
        {requirements && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <span>Matched against:</span>
            {(requirements.must_have ?? []).map((s) => (
              <Badge key={s.name} tone="info">
                {s.name}
              </Badge>
            ))}
            {(requirements.nice_to_have ?? []).map((s) => (
              <Badge key={s.name}>{s.name}</Badge>
            ))}
            {run.settings?.only_available && <span>· only available people</span>}
            {run.settings?.judge_model && <span>· judge {run.settings.judge_model}</span>}
          </div>
        )}
      </header>

      {run.results.length === 0 ? (
        <Card>
          <CardContent>
            <EmptyState icon={UserSearch} title="Nobody matched">
              No employee with a searchable resume fits these requirements. Loosen the requirements or the availability
              filter and run again.
            </EmptyState>
          </CardContent>
        </Card>
      ) : (
        <ol className="space-y-4" aria-label="Ranked candidates">
          {run.results.map((r) => (
            <li key={r.employee_id}>
              <ResultCard result={r} judgeWeight={judgeWeight} />
            </li>
          ))}
        </ol>
      )}
      <p className="mt-6 text-xs text-muted-foreground">
        The ranking supports a decision; it doesn&apos;t make one. Check the evidence, talk to the person and their
        manager.
      </p>
    </>
  );
}

function RunSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading the results">
      <Skeleton className="h-10 w-96" />
      {Array.from({ length: 3 }, (_, i) => (
        <Skeleton key={i} className="h-48 w-full rounded-xl" />
      ))}
    </div>
  );
}
