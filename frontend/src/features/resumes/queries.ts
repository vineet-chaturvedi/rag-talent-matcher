import "server-only";

import { request } from "@/lib/api/client";
import type { ResumeStatus } from "@/lib/api/types";

/** Resumes per page in the admin list. One more is requested to know whether a next page exists. */
export const RESUMES_PAGE_SIZE = 25;

export function listResumes({ status, page }: { status?: ResumeStatus; page: number }) {
  return request((api) =>
    api.GET("/api/resumes", {
      params: { query: { status, limit: RESUMES_PAGE_SIZE + 1, offset: (page - 1) * RESUMES_PAGE_SIZE } },
    }),
  );
}

/** Count per pipeline stage, worker state, number of indexed chunks. Used by the dashboard too. */
export const getQueueStats = () => request((api) => api.GET("/api/resumes/stats"));
