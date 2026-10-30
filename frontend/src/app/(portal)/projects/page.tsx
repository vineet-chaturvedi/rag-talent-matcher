import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { SectionBoundary } from "@/components/section-boundary";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NewProjectForm } from "@/features/projects/components/new-project-form";
import { ProjectList, ProjectListSkeleton } from "@/features/projects/components/project-list";

export const metadata: Metadata = { title: "Projects & matching" };

/** Projects and their roles; the starting point for matching people to a role. */
export default function ProjectsPage() {
  return (
    <>
      <PageHeader title="Projects & matching" description="Roles to fill, and the ranked people who could fill them." />
      <div className="space-y-6">
        <SectionBoundary title="The projects">
          <Suspense fallback={<ProjectListSkeleton />}>
            <ProjectList />
          </Suspense>
        </SectionBoundary>
        <Card>
          <CardHeader>
            <div className="space-y-1">
              <CardTitle>New project</CardTitle>
              <CardDescription>Then add the roles to fill on the project&apos;s page.</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <NewProjectForm />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
