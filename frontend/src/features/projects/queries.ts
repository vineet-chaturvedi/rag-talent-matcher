import "server-only";

import { request } from "@/lib/api/client";

/** Projects, roles and match runs: the reads behind the Step 12b pages (server-only, typed). */

export const listProjects = () => request((api) => api.GET("/api/projects"));

export const getProject = (projectId: number) =>
  request((api) => api.GET("/api/projects/{project_id}", { params: { path: { project_id: projectId } } }));

export const getRole = (roleId: number) =>
  request((api) => api.GET("/api/roles/{role_id}", { params: { path: { role_id: roleId } } }));

export const listMatchRuns = (roleId: number) =>
  request((api) => api.GET("/api/roles/{role_id}/match-runs", { params: { path: { role_id: roleId } } }));

export const getMatchRun = (runId: number) =>
  request((api) => api.GET("/api/match-runs/{run_id}", { params: { path: { run_id: runId } } }));
