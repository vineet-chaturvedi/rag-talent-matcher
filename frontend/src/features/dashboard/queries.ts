import "server-only";

import { request } from "@/lib/api/client";
import type { ApiResult } from "@/lib/api/errors";
import type { Health } from "@/lib/api/types";

/**
 * The dashboard's data (its part of the Data Access Layer). Server-only; every call is typed end to
 * end by the generated schema, and returns an ApiResult so the cards can show problems in place.
 *
 * No caching on purpose: these numbers change while resumes are processed, and each call is a few
 * milliseconds of SQL. They run at request time inside <Suspense>, so they never delay the page frame.
 */

export const getOverview = () => request((api) => api.GET("/api/overview"));

export const getProjects = () => request((api) => api.GET("/api/projects"));

/**
 * GET /api/health answers 503 when the database or Ollama is unreachable, WITH a full report in the
 * body. For the dashboard that report is the useful part, so 503 counts as data here.
 */
export async function getHealth(): Promise<ApiResult<Health>> {
  return request(async (api) => {
    const result = await api.GET("/api/health");
    if (result.response.status === 503 && result.error) {
      return { data: result.error as Health, response: new Response(null, { status: 200 }) };
    }
    return result;
  });
}
