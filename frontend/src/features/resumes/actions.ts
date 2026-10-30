"use server";

import { refresh } from "next/cache";

import { type ActionResult, toActionResult } from "@/lib/actions";
import { request } from "@/lib/api/client";
import { plural } from "@/lib/utils";

/**
 * Server Actions for resumes (admins). Each one: call FastAPI (which checks the admin role and
 * answers 403 to anyone else), then `refresh()` so the page re-renders with the new state.
 *
 * Ids arrive as BOUND arguments (`retryResume.bind(null, id)`): Next.js encrypts them in the page, but
 * they are still validated here, because every Server Action is a public endpoint.
 */

function validId(id: unknown): id is number {
  return Number.isInteger(id) && (id as number) > 0;
}

export async function retryResume(resumeId: number): Promise<ActionResult> {
  if (!validId(resumeId)) return { ok: false, message: "Invalid resume." };
  const result = await request((api) =>
    api.POST("/api/resumes/{resume_id}/retry", { params: { path: { resume_id: resumeId } } }),
  );
  if (result.ok) refresh();
  return toActionResult(result, () => "Queued again.");
}

export async function deleteResume(resumeId: number): Promise<ActionResult> {
  if (!validId(resumeId)) return { ok: false, message: "Invalid resume." };
  const result = await request((api) =>
    api.DELETE("/api/resumes/{resume_id}", { params: { path: { resume_id: resumeId } } }),
  );
  if (result.ok) refresh();
  return toActionResult(result, () => "Deleted.");
}

export async function reextractAll(): Promise<ActionResult> {
  const result = await request((api) => api.POST("/api/resumes/reextract"));
  if (result.ok) refresh();
  return toActionResult(result, (data) => `${plural(data.requeued, "resume")} sent back to AI reading.`);
}

export async function reembedAll(): Promise<ActionResult> {
  const result = await request((api) => api.POST("/api/resumes/reembed"));
  if (result.ok) refresh();
  return toActionResult(result, (data) => `${plural(data.requeued, "resume")} queued for re-indexing.`);
}
