import { ArrowLeft } from "lucide-react";
import type { Metadata, Route } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ActionButton } from "@/components/action-button";
import { SectionBoundary } from "@/components/section-boundary";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { setRoleStatus } from "@/features/projects/actions";
import { MatchForm } from "@/features/projects/components/match-form";
import { RequirementsPanel } from "@/features/projects/components/requirements-panel";
import { RoleStatusBadge } from "@/features/projects/components/role-status-badge";
import { RunHistory } from "@/features/projects/components/run-history";
import { getProject, getRole } from "@/features/projects/queries";
import { idParam } from "@/lib/search-params";
import { formatDate } from "@/lib/utils";

export const metadata: Metadata = { title: "Role" };

/**
 * The role workspace: the description, what the AI understood from it (correctable), starting a
 * match, and every earlier match run. This is where the RAG pipeline meets the person staffing it.
 */
export default function RolePage(props: PageProps<"/roles/[id]">) {
  return (
    <SectionBoundary title="This role">
      <Suspense fallback={<Skeleton className="h-96 w-full rounded-xl" />}>
        <Role params={props.params} />
      </Suspense>
    </SectionBoundary>
  );
}

async function Role({ params }: Pick<PageProps<"/roles/[id]">, "params">) {
  const id = idParam((await params).id);
  if (id === null) notFound();
  const result = await getRole(id);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <Alert>{result.message}</Alert>;
  }
  const role = result.data;
  const project = await getProject(role.project_id);

  return (
    <>
      <Link
        href={`/projects/${role.project_id}` as Route}
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden /> {project.ok ? project.data.name : "Project"}
      </Link>
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight">{role.title}</h1>
            <RoleStatusBadge status={role.status} />
          </div>
          <p className="text-sm text-muted-foreground">
            {role.allocation_percent}% · {role.headcount} {role.headcount === 1 ? "person" : "people"}
            {role.location && ` · ${role.location}`}
            {role.start_date && ` · from ${formatDate(role.start_date)}`}
            {role.min_experience_years != null && ` · ${role.min_experience_years}+ years`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {role.status === "open" ? (
            <>
              <ActionButton
                action={setRoleStatus.bind(null, role.id, "filled")}
                label="Mark filled"
                pendingLabel="Saving…"
              />
              <ActionButton
                action={setRoleStatus.bind(null, role.id, "closed")}
                label="Close"
                pendingLabel="Saving…"
                variant="ghost"
              />
            </>
          ) : (
            <ActionButton action={setRoleStatus.bind(null, role.id, "open")} label="Reopen" pendingLabel="Saving…" />
          )}
        </div>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-[1fr_24rem]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Description</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed whitespace-pre-line">{role.description}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <div className="space-y-1">
                <CardTitle>Requirements</CardTitle>
                <CardDescription>What matching looks for. Correct anything the AI got wrong.</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <RequirementsPanel
                key={JSON.stringify(role.requirements)}
                roleId={role.id}
                requirements={role.requirements ?? null}
              />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Find best matches</CardTitle>
            </CardHeader>
            <CardContent>
              {role.requirements ? (
                <MatchForm roleId={role.id} />
              ) : (
                <p className="text-sm text-muted-foreground">First let the AI read the description (left).</p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Earlier runs</CardTitle>
            </CardHeader>
            <CardContent>
              <Suspense fallback={<Skeleton className="h-24 w-full" />}>
                <RunHistory roleId={role.id} />
              </Suspense>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
