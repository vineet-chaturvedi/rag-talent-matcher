import Link from "next/link";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate } from "@/lib/utils";

import { getProjects } from "../queries";

/** Projects with their roles, and whether each role's requirements are parsed (Step 7). */
export async function ProjectsCard() {
  const projects = await getProjects();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Projects and open roles</CardTitle>
        <CardAction>
          <Button asChild variant="link" size="sm" className="h-auto px-0">
            <Link href="/projects">Open projects</Link>
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {!projects.ok && <Alert>{projects.message}</Alert>}
        {projects.ok && projects.data.length === 0 && <p className="text-sm text-muted-foreground">No projects yet.</p>}
        {projects.ok && projects.data.length > 0 && (
          <ul className="divide-y">
            {projects.data.map((project) => (
              <li key={project.id} className="py-3 first:pt-0 last:pb-0">
                <p className="text-sm font-medium">{project.name}</p>
                <ul className="mt-1.5 space-y-1.5">
                  {project.roles.map((role) => (
                    <li
                      key={role.id}
                      className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground"
                    >
                      <span className="text-foreground">{role.title}</span>
                      <span>
                        · {role.allocation_percent}%{role.start_date ? ` · from ${formatDate(role.start_date)}` : ""}
                      </span>
                      <Badge tone={role.requirements ? "success" : "warning"}>
                        {role.requirements ? "requirements parsed" : "not parsed"}
                      </Badge>
                    </li>
                  ))}
                  {project.roles.length === 0 && <li className="text-sm text-muted-foreground">No roles yet.</li>}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function ProjectsCardSkeleton() {
  return (
    <Card role="status" aria-label="Loading projects">
      <CardHeader>
        <CardTitle>Projects and open roles</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {Array.from({ length: 3 }, (_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-4 w-full max-w-md" />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
