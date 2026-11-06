import { FileSearch } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { ActionButton } from "@/components/action-button";
import { AutoRefresh } from "@/components/auto-refresh";
import { EmptyState } from "@/components/empty-state";
import { Pagination } from "@/components/pagination";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { ResumeStatus } from "@/lib/api/types";
import { formatBytes, formatDateTime, plural } from "@/lib/utils";

import { deleteResume, retryResume } from "../actions";
import { isInProgress, STATUS_LABEL } from "../labels";
import { listResumes, RESUMES_PAGE_SIZE } from "../queries";
import { ResumeFileLinks } from "./resume-file-links";
import { ResumeStatusBadge } from "./resume-status-badge";

/** The admin list of current resumes: who, which file, where in the pipeline, what went wrong. */
export async function ResumesTable({ status, page }: { status?: ResumeStatus; page: number }) {
  const result = await listResumes({ status, page });
  if (!result.ok) return <Alert>{result.message}</Alert>;

  const rows = result.data.slice(0, RESUMES_PAGE_SIZE);
  const hasNext = result.data.length > RESUMES_PAGE_SIZE;

  if (rows.length === 0) {
    return (
      <EmptyState icon={FileSearch} title={status ? `No resumes are "${STATUS_LABEL[status]}"` : "No resumes yet"}>
        {status ? "Choose another status above." : "Upload resumes with the box above."}
      </EmptyState>
    );
  }

  return (
    <>
      {/* Live while the worker is busy with anything on this page. */}
      {rows.some((r) => isInProgress(r.status)) && <AutoRefresh seconds={5} />}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Employee</TableHead>
            <TableHead>File</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Uploaded</TableHead>
            <TableHead>
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((resume) => (
            <TableRow key={resume.id}>
              <TableCell>
                <Link href={`/employees/${resume.employee_id}` as Route} className="font-medium hover:underline">
                  {resume.employee_name}
                </Link>
                <span className="block text-xs text-muted-foreground">{resume.employee_code}</span>
              </TableCell>
              <TableCell className="max-w-64">
                <span className="block truncate" title={resume.original_filename}>
                  {resume.original_filename}
                </span>
                <span className="text-xs text-muted-foreground">
                  {formatBytes(resume.file_size_bytes)}
                  {resume.page_count ? ` · ${plural(resume.page_count, "page")}` : ""}
                </span>
              </TableCell>
              <TableCell className="max-w-72">
                <ResumeStatusBadge status={resume.status} isCurrent={resume.is_current} />
                {resume.error_message && (
                  <span className="mt-1 block text-xs text-destructive">{resume.error_message}</span>
                )}
                {resume.attempts > 0 && resume.status !== "ready" && (
                  <span className="mt-1 block text-xs text-muted-foreground">attempts: {resume.attempts}</span>
                )}
              </TableCell>
              <TableCell className="text-xs whitespace-nowrap text-muted-foreground">
                {formatDateTime(resume.created_at)}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  <ResumeFileLinks resume={resume} />
                  {resume.status === "failed" && (
                    <ActionButton action={retryResume.bind(null, resume.id)} label="Retry" pendingLabel="Retrying…" />
                  )}
                  <ActionButton
                    action={deleteResume.bind(null, resume.id)}
                    label="Delete"
                    pendingLabel="Deleting…"
                    variant="ghost"
                    confirm={{
                      title: `Delete ${resume.original_filename}?`,
                      description: `The file, its AI profile and its search index entries are removed for ${resume.employee_name}. An older version, if any, becomes current. This can't be undone.`,
                      confirmLabel: "Delete resume",
                    }}
                  />
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Pagination pathname="/resumes" params={{ status }} page={page} hasNext={hasNext} />
    </>
  );
}

export function ResumesTableSkeleton() {
  return (
    <div className="space-y-3" role="status" aria-label="Loading resumes">
      {Array.from({ length: 8 }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}
