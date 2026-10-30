import "server-only";

import { request } from "@/lib/api/client";
import type { AvailabilityStatus } from "@/lib/api/types";

export const EMPLOYEES_PAGE_SIZE = 25;

/** One page of employees; one extra row is requested to know whether there is a next page. */
export function listEmployees({
  search,
  availability,
  page,
}: {
  search?: string;
  availability?: AvailabilityStatus;
  page: number;
}) {
  return request((api) =>
    api.GET("/api/employees", {
      params: {
        query: {
          search,
          availability,
          limit: EMPLOYEES_PAGE_SIZE + 1,
          offset: (page - 1) * EMPLOYEES_PAGE_SIZE,
        },
      },
    }),
  );
}

export const getEmployee = (employeeId: number) =>
  request((api) => api.GET("/api/employees/{employee_id}", { params: { path: { employee_id: employeeId } } }));

/** The AI-extracted profile of one resume (404 until the resume has been read by the LLM). */
export const getProfile = (resumeId: number) =>
  request((api) => api.GET("/api/resumes/{resume_id}/profile", { params: { path: { resume_id: resumeId } } }));
