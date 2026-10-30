import type { Metadata } from "next";
import { Suspense } from "react";

import { ComingSoon } from "@/components/coming-soon";
import { PageHeader } from "@/components/layout/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminOnly } from "@/features/auth/components/admin-only";

export const metadata: Metadata = { title: "Resumes" };

const PLANNED = [
  "Admins: drag-and-drop bulk upload (files named EMP-1001_name.pdf)",
  "Live processing status for every resume, retry and delete",
  "Re-extract or re-index everything after a model or prompt change",
] as const;

export default function ResumesPage() {
  return (
    <>
      <PageHeader title="Resumes" description="The knowledge base: uploaded resumes and their processing status." />
      <Suspense fallback={<Skeleton className="h-32 w-full rounded-xl" />}>
        <AdminOnly>
          <ComingSoon step={12} items={PLANNED} />
        </AdminOnly>
      </Suspense>
    </>
  );
}
