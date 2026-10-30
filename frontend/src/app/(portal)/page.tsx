import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { SectionBoundary } from "@/components/section-boundary";
import { Greeting } from "@/features/dashboard/components/greeting";
import { HealthCard, HealthCardSkeleton } from "@/features/dashboard/components/health-card";
import { OverviewTiles, OverviewTilesSkeleton } from "@/features/dashboard/components/overview-tiles";
import { PipelineCard, PipelineCardSkeleton } from "@/features/dashboard/components/pipeline-card";
import { ProjectsCard, ProjectsCardSkeleton } from "@/features/dashboard/components/projects-card";

export const metadata: Metadata = { title: "Dashboard" };

/**
 * The dashboard: the state of the knowledge base and the AI services.
 *
 * How it renders (streaming):
 *   1. Instantly: the heading and four skeleton blocks (static, prerendered).
 *   2. Each block's Server Component calls FastAPI on the server, in parallel with the others.
 *   3. Each block replaces its skeleton the moment ITS data is ready; a slow Ollama health check
 *      doesn't hold back the numbers.
 * Each block also has its own error boundary, so one failing block can't take the page down.
 */
export default function DashboardPage() {
  return (
    <>
      <PageHeader
        title={
          <Suspense fallback="Dashboard">
            <Greeting />
          </Suspense>
        }
        description="The state of the knowledge base and the AI services, right now."
      />

      <div className="space-y-6">
        <SectionBoundary title="The numbers">
          <Suspense fallback={<OverviewTilesSkeleton />}>
            <OverviewTiles />
          </Suspense>
        </SectionBoundary>

        <div className="grid gap-6 lg:grid-cols-2">
          <SectionBoundary title="System health">
            <Suspense fallback={<HealthCardSkeleton />}>
              <HealthCard />
            </Suspense>
          </SectionBoundary>
          <SectionBoundary title="The resume pipeline">
            <Suspense fallback={<PipelineCardSkeleton />}>
              <PipelineCard />
            </Suspense>
          </SectionBoundary>
        </div>

        <SectionBoundary title="Projects">
          <Suspense fallback={<ProjectsCardSkeleton />}>
            <ProjectsCard />
          </Suspense>
        </SectionBoundary>
      </div>
    </>
  );
}
