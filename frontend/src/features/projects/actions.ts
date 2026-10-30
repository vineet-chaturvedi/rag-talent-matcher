"use server";

import type { Route } from "next";
import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { z } from "zod";

import { type ActionResult, toActionResult } from "@/lib/actions";
import { request } from "@/lib/api/client";
import type { RoleStatus } from "@/lib/api/types";

import { type FormState, formValues, matchSchema, projectSchema, requirementsSchema, roleSchema } from "./schemas";

/**
 * Server Actions for projects, roles and matching (Step 12b). Every signed-in user may use them
 * (FastAPI checks the session). Pattern for each: validate with zod -> call FastAPI -> redirect to
 * the new thing, or refresh() the current page, or return the error for the form.
 */

const validId = (id: unknown): id is number => Number.isInteger(id) && (id as number) > 0;

function invalid(error: z.ZodError, formData: FormData): FormState {
  return { fieldErrors: z.flattenError(error).fieldErrors, values: formValues(formData) };
}

export async function createProject(_previous: FormState, formData: FormData): Promise<FormState> {
  const parsed = projectSchema.safeParse(formValues(formData));
  if (!parsed.success) return invalid(parsed.error, formData);
  const result = await request((api) => api.POST("/api/projects", { body: parsed.data }));
  if (!result.ok) return { message: result.message, values: formValues(formData) };
  redirect(`/projects/${result.data.id}` as Route);
}

export async function createRole(projectId: number, _previous: FormState, formData: FormData): Promise<FormState> {
  if (!validId(projectId)) return { message: "Invalid project." };
  const parsed = roleSchema.safeParse(formValues(formData));
  if (!parsed.success) return invalid(parsed.error, formData);
  const result = await request((api) =>
    api.POST("/api/projects/{project_id}/roles", { params: { path: { project_id: projectId } }, body: parsed.data }),
  );
  if (!result.ok) return { message: result.message, values: formValues(formData) };
  redirect(`/roles/${result.data.id}` as Route);
}

export async function setRoleStatus(roleId: number, status: RoleStatus): Promise<ActionResult> {
  if (!validId(roleId) || !["open", "filled", "closed"].includes(status)) return { ok: false, message: "Invalid." };
  const result = await request((api) =>
    api.PATCH("/api/roles/{role_id}", { params: { path: { role_id: roleId } }, body: { status } }),
  );
  if (result.ok) refresh();
  return toActionResult(result, () => "Saved.");
}

/** The LLM reads the role description (Step 7). Slow on a CPU: 30-60 s with the 7B model. */
export async function parseRequirements(roleId: number): Promise<ActionResult> {
  if (!validId(roleId)) return { ok: false, message: "Invalid role." };
  const result = await request((api) =>
    api.POST("/api/roles/{role_id}/requirements/parse", { params: { path: { role_id: roleId } } }),
  );
  if (result.ok) refresh();
  return toActionResult(
    result,
    (role) => `Read by ${role.requirements?.parsed_by ?? "the AI"}. Check the result below.`,
  );
}

/** A person corrects what the AI parsed. FastAPI normalises skill names ("k8s" -> "Kubernetes"). */
export async function saveRequirements(roleId: number, _previous: FormState, formData: FormData): Promise<FormState> {
  if (!validId(roleId)) return { message: "Invalid role." };
  let payload: unknown;
  try {
    payload = JSON.parse(String(formData.get("payload") ?? ""));
  } catch {
    return { message: "The form could not be read. Reload the page and try again." };
  }
  const parsed = requirementsSchema.safeParse(payload);
  if (!parsed.success) {
    return { message: parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ") };
  }
  const result = await request((api) =>
    api.PUT("/api/roles/{role_id}/requirements", {
      params: { path: { role_id: roleId } },
      // FastAPI sets edited_by_user = true itself and keeps who parsed it originally.
      body: { ...parsed.data, edited_by_user: true },
    }),
  );
  if (!result.ok) return { message: result.message };
  refresh();
  return { ok: true, message: "Saved. Skill names were normalised; new matches use these requirements." };
}

/**
 * Start a match run (Step 8): retrieval and rule scoring finish in about a second; the LLM judge then
 * reads the top N in the background. We go straight to the run's page, which refreshes itself while
 * the judge works.
 */
export async function startMatch(roleId: number, _previous: FormState, formData: FormData): Promise<FormState> {
  if (!validId(roleId)) return { message: "Invalid role." };
  const parsed = matchSchema.safeParse(formValues(formData));
  if (!parsed.success) return invalid(parsed.error, formData);
  const body = { ...parsed.data, judge_top_n: Math.min(parsed.data.judge_top_n, parsed.data.top_k) };
  const result = await request((api) =>
    api.POST("/api/roles/{role_id}/match", { params: { path: { role_id: roleId } }, body }),
  );
  if (!result.ok) return { message: result.message, values: formValues(formData) };
  redirect(`/match-runs/${result.data.id}` as Route);
}
