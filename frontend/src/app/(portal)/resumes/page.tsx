import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { SectionBoundary } from "@/components/section-boundary";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminOnly } from "@/features/auth/components/admin-only";
import { PIPELINE_STAGES } from "@/features/resumes/labels";
import { getQueueStats } from "@/features/resumes/queries";
import { BulkUpload } from "@/features/resumes/components/bulk-upload";
import { MaintenanceCard } from "@/features/resumes/components/maintenance-card";
import { ResumesTable, ResumesTableSkeleton } from "@/features/resumes/components/resumes-table";
import { StatusFilter } from "@/features/resumes/components/status-filter";
import { enumParam, pageParam } from "@/lib/search-params";

export const metadata: Metadata = { title: "Resumes" };

const STATUSES = PIPELINE_STAGES.map((s) => s.status);

/**
 * Resumes (admins): the knowledge base's intake. Upload, watch the pipeline, fix failures.
 * Static: the heading. Streamed: the admin check, then the list for the URL's ?status= and ?page=.
 */
export default function ResumesPage(props: PageProps<"/resumes">) {
  return (
    <>
      <PageHeader title="Resumes" description="The knowledge base: upload resumes and follow their processing." />
      <Suspense fallback={<Skeleton className="h-48 w-full rounded-xl" />}>
        <AdminOnly>
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <div className="space-y-1">
                  <CardTitle>Upload</CardTitle>
                  <CardDescription>
                    A new file for someone who already has a resume becomes their current version.
                  </CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <BulkUpload />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Current resumes</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <SectionBoundary title="The resume list">
                  <Suspense fallback={<ResumesTableSkeleton />}>
                    <ResumeList searchParams={props.searchParams} />
                  </Suspense>
                </SectionBoundary>
              </CardContent>
            </Card>

            <MaintenanceCard />
          </div>
        </AdminOnly>
      </Suspense>
    </>
  );
}

async function ResumeList({ searchParams }: Pick<PageProps<"/resumes">, "searchParams">) {
  const params = await searchParams;
  const status = enumParam(params.status, STATUSES);
  const page = pageParam(params.page);
  const stats = await getQueueStats();
  return (
    <>
      <StatusFilter stats={stats.ok ? stats.data : null} active={status} />
      <ResumesTable status={status} page={page} />
    </>
  );
}
