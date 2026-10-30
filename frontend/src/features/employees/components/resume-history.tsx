import { Suspense } from "react";

import { ActionButton } from "@/components/action-button";
import { AutoRefresh } from "@/components/auto-refresh";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { IfAdmin } from "@/features/auth/components/if-admin";
import { deleteResume, retryResume } from "@/features/resumes/actions";
import { ResumeStatusBadge } from "@/features/resumes/components/resume-status-badge";
import { isInProgress } from "@/features/resumes/labels";
import type { Resume } from "@/lib/api/types";
import { formatBytes, formatDateTime } from "@/lib/utils";

import { UploadResume } from "./upload-resume";

/** Every uploaded version of this person's resume, newest first; admins can upload, retry, delete. */
export function ResumeHistory({ employeeId, resumes }: { employeeId: number; resumes: Resume[] }) {
  const sorted = [...resumes].sort((a, b) => b.id - a.id);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Resume versions</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {sorted.some((r) => isInProgress(r.status)) && <AutoRefresh seconds={5} />}
        {sorted.length === 0 && <p className="text-sm text-muted-foreground">No resume uploaded yet.</p>}
        <ul className="divide-y">
          {sorted.map((resume) => (
            <li key={resume.id} className="space-y-1.5 py-3 first:pt-0 last:pb-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="min-w-0 truncate text-sm font-medium" title={resume.original_filename}>
                  {resume.original_filename}
                </span>
                {resume.is_current && <Badge tone="info">current</Badge>}
                <ResumeStatusBadge status={resume.status} />
              </div>
              <p className="text-xs text-muted-foreground">
                {formatBytes(resume.file_size_bytes)} · uploaded {formatDateTime(resume.created_at)}
              </p>
              {resume.error_message && <p className="text-xs text-destructive">{resume.error_message}</p>}
              <Suspense>
                <IfAdmin>
                  <div className="flex flex-wrap gap-2">
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
                        description:
                          "The file, its AI profile and its search entries are removed. If it is the current version, the newest older version becomes current. This can't be undone.",
                        confirmLabel: "Delete resume",
                      }}
                    />
                  </div>
                </IfAdmin>
              </Suspense>
            </li>
          ))}
        </ul>
        <Suspense>
          <IfAdmin>
            <div className="border-t pt-4">
              <UploadResume employeeId={employeeId} />
            </div>
          </IfAdmin>
        </Suspense>
      </CardContent>
    </Card>
  );
}
