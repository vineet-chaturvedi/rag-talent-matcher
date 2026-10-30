import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { SectionBoundary } from "@/components/section-boundary";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { projectStatusLabel, projectStatusTone } from "@/features/projects/labels";
import { NewRoleForm } from "@/features/projects/components/new-role-form";
import { RoleRow } from "@/features/projects/components/role-row";
import { getProject } from "@/features/projects/queries";
import { idParam } from "@/lib/search-params";
import { formatDate } from "@/lib/utils";

export const metadata: Metadata = { title: "Project" };

export default function ProjectPage(props: PageProps<"/projects/[id]">) {
  return (
    <>
      <Link
        href="/projects"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden /> Projects
      </Link>
      <SectionBoundary title="This project">
        <Suspense fallback={<Skeleton className="h-64 w-full rounded-xl" />}>
          <Project params={props.params} />
        </Suspense>
      </SectionBoundary>
    </>
  );
}

async function Project({ params }: Pick<PageProps<"/projects/[id]">, "params">) {
  const id = idParam((await params).id);
  if (id === null) notFound();
  const result = await getProject(id);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <Alert>{result.message}</Alert>;
  }
  const project = result.data;
  return (
    <>
      <header className="mb-6 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight">{project.name}</h1>
          <Badge tone={projectStatusTone(project.status)}>{projectStatusLabel(project.status)}</Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          {[
            project.client_name,
            project.start_date && `from ${formatDate(project.start_date)}`,
            project.end_date && `until ${formatDate(project.end_date)}`,
          ]
            .filter(Boolean)
            .join(" · ") || "No dates yet"}
        </p>
        {project.description && <p className="max-w-3xl text-sm">{project.description}</p>}
      </header>
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Roles ({project.roles.length})</CardTitle>
          </CardHeader>
          <CardContent>
            {project.roles.length === 0 ? (
              <p className="text-sm text-muted-foreground">No roles yet: add the first one below.</p>
            ) : (
              <ul className="-mx-3 divide-y">
                {project.roles.map((role) => (
                  <li key={role.id}>
                    <RoleRow role={role} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <div className="space-y-1">
              <CardTitle>Add a role</CardTitle>
              <CardDescription>
                Describe the position; the AI reads the description to find what matters.
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <NewRoleForm projectId={project.id} />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
