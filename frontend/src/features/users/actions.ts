"use server";

import { refresh } from "next/cache";
import { z } from "zod";

import { type ActionResult, toActionResult } from "@/lib/actions";
import { request } from "@/lib/api/client";
import type { UserRole } from "@/lib/api/types";
import { type FormState, formValues } from "@/lib/forms";

import { changePasswordSchema, createUserSchema, resetPasswordSchema } from "./schemas";

/**
 * Server Actions for portal accounts (Step 12c). FastAPI enforces every rule: admin only, unique
 * email, password policy, never remove the last admin, never lock yourself out. These actions
 * validate the input first, so people get the message next to the field.
 *
 * Passwords are never sent back to the page (not even in `values` after an error).
 */

const validId = (id: unknown): id is number => Number.isInteger(id) && (id as number) > 0;

function withoutSecrets(formData: FormData): Record<string, string> {
  const values = formValues(formData);
  for (const key of Object.keys(values)) if (key.includes("password")) delete values[key];
  return values;
}

export async function createUser(_previous: FormState, formData: FormData): Promise<FormState> {
  const parsed = createUserSchema.safeParse(formValues(formData));
  if (!parsed.success) {
    return { fieldErrors: z.flattenError(parsed.error).fieldErrors, values: withoutSecrets(formData) };
  }
  const result = await request((api) => api.POST("/api/users", { body: parsed.data }));
  if (!result.ok) return { message: result.message, values: withoutSecrets(formData) };
  refresh();
  return {
    ok: true,
    message: `${result.data.full_name} can now sign in as ${result.data.email}. Share the password with them in person or by phone, not by email.`,
  };
}

export async function setUserRole(userId: number, role: UserRole): Promise<ActionResult> {
  if (!validId(userId) || !["admin", "resource_manager"].includes(role)) return { ok: false, message: "Invalid." };
  const result = await request((api) =>
    api.PATCH("/api/users/{user_id}", { params: { path: { user_id: userId } }, body: { role } }),
  );
  if (result.ok) refresh();
  return toActionResult(
    result,
    (u) => `${u.full_name} is now ${role === "admin" ? "an administrator" : "a resource manager"}.`,
  );
}

export async function setUserActive(userId: number, active: boolean): Promise<ActionResult> {
  if (!validId(userId) || typeof active !== "boolean") return { ok: false, message: "Invalid." };
  const result = await request((api) =>
    api.PATCH("/api/users/{user_id}", { params: { path: { user_id: userId } }, body: { is_active: active } }),
  );
  if (result.ok) refresh();
  return toActionResult(result, (u) =>
    active ? `${u.full_name} can sign in again.` : `${u.full_name} can no longer sign in. Their history is kept.`,
  );
}

export async function resetPassword(userId: number, _previous: FormState, formData: FormData): Promise<FormState> {
  if (!validId(userId)) return { message: "Invalid user." };
  const parsed = resetPasswordSchema.safeParse(formValues(formData));
  if (!parsed.success) return { fieldErrors: z.flattenError(parsed.error).fieldErrors };
  const result = await request((api) =>
    api.PATCH("/api/users/{user_id}", {
      params: { path: { user_id: userId } },
      body: { password: parsed.data.password },
    }),
  );
  if (!result.ok) return { message: result.message };
  return {
    ok: true,
    message: `New password set for ${result.data.full_name}. Their current sessions keep working until they expire.`,
  };
}

/** Any signed-in user, for their OWN account. FastAPI checks the current password. */
export async function changeOwnPassword(_previous: FormState, formData: FormData): Promise<FormState> {
  const parsed = changePasswordSchema.safeParse(formValues(formData));
  if (!parsed.success) return { fieldErrors: z.flattenError(parsed.error).fieldErrors };
  // A wrong current password is a 400 from FastAPI; a 401 would mean the session itself ended.
  const result = await request((api) =>
    api.POST("/api/auth/change-password", {
      body: { current_password: parsed.data.current_password, new_password: parsed.data.new_password },
    }),
  );
  if (!result.ok) {
    return result.status === 400 && /current password/i.test(result.message)
      ? { fieldErrors: { current_password: [result.message] } }
      : { message: result.message };
  }
  return { ok: true, message: "Your password was changed. Use it the next time you sign in." };
}
