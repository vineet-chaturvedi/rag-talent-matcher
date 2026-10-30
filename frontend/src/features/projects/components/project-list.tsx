import { FolderKanban } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate } from "@/lib/utils";

import { projectStatusLabel, projectStatusTone } from "../labels";
import { listProjects } from "../queries";
import { RoleRow } from "./role-row";

/** All projects, each with its roles. Open roles first, so the work to do is on top. */
export async function ProjectList() {
  const result = await listProjects();
  if (!result.ok) return <Alert>{result.message}</Alert>;
  if (result.data.length === 0) {
    return (
      <Card>
        <CardContent>
          <EmptyState icon={FolderKanban} title="No projects yet">
            Create the first project below, then add the roles you need to fill.
          </EmptyState>
        </CardContent>
      </Card>
    );
  }
  const order = { open: 0, filled: 1, closed: 2 } as const;
  return (
    <div className="space-y-4">
      {result.data.map((project) => (
        <Card key={project.id}>
          <CardHeader>
            <div className="min-w-0 space-y-1">
              <CardTitle>
                <Link href={`/projects/${project.id}` as Route} className="hover:underline">
                  {project.name}
                </Link>
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                {project.client_name && `${project.client_name} · `}
                {project.start_date ? `starts ${formatDate(project.start_date)}` : "no start date"}
              </p>
            </div>
            <CardAction>
              <Badge tone={projectStatusTone(project.status)}>{projectStatusLabel(project.status)}</Badge>
            </CardAction>
          </CardHeader>
          <CardContent>
            {project.roles.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No roles yet.{" "}
                <Link href={`/projects/${project.id}` as Route} className="text-primary hover:underline">
                  Add one
                </Link>
              </p>
            ) : (
              <ul className="-mx-3 divide-y">
                {[...project.roles]
                  .sort((a, b) => order[a.status] - order[b.status])
                  .map((role) => (
                    <li key={role.id}>
                      <RoleRow role={role} />
                    </li>
                  ))}
              </ul>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function ProjectListSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading projects">
      {Array.from({ length: 3 }, (_, i) => (
        <Skeleton key={i} className="h-40 w-full rounded-xl" />
      ))}
    </div>
  );
}
