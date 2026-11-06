import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { SectionBoundary } from "@/components/section-boundary";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminOnly } from "@/features/auth/components/admin-only";
import { FeedbackTable, FeedbackTableSkeleton } from "@/features/feedback/components/feedback-table";
import { enumParam, pageParam } from "@/lib/search-params";

export const metadata: Metadata = { title: "Feedback" };

const TARGETS = ["match_result", "agent_answer"] as const;
const RATINGS = ["up", "down"] as const;

/**
 * Feedback (admins, Step 14c): every 👍 / 👎 people gave on match results and assistant answers.
 * Static: the heading. Streamed: the admin check, then the list for the URL's filters.
 */
export default function FeedbackPage(props: PageProps<"/feedback">) {
  return (
    <>
      <PageHeader
        title="Feedback"
        description="What colleagues said about the matches and the assistant's answers. Each rating is a test case for improving the system."
      />
      <Suspense fallback={<Skeleton className="h-48 w-full rounded-xl" />}>
        <AdminOnly>
          <Card>
            <CardContent>
              <SectionBoundary title="The feedback list">
                <Suspense fallback={<FeedbackTableSkeleton />}>
                  <FeedbackList searchParams={props.searchParams} />
                </Suspense>
              </SectionBoundary>
            </CardContent>
          </Card>
        </AdminOnly>
      </Suspense>
    </>
  );
}

async function FeedbackList({ searchParams }: Pick<PageProps<"/feedback">, "searchParams">) {
  const params = await searchParams;
  return (
    <FeedbackTable
      target={enumParam(params.target, TARGETS)}
      rating={enumParam(params.rating, RATINGS)}
      page={pageParam(params.page)}
    />
  );
}
