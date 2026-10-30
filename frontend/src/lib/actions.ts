import type { ApiResult } from "@/lib/api/errors";

/**
 * What every Server Action that changes data returns to the page: did it work, and a sentence to show.
 * Kept tiny and serialisable (it travels from the server to the browser).
 */
export type ActionResult = { ok: boolean; message: string } | null;

/** Turn a backend call's result into an ActionResult with a success sentence of our choosing. */
export function toActionResult<T>(result: ApiResult<T>, success: (data: T) => string): ActionResult {
  return result.ok ? { ok: true, message: success(result.data) } : { ok: false, message: result.message };
}
