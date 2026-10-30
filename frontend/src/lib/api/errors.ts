/**
 * Turning backend failures into messages a person can act on.
 *
 * FastAPI sends errors as JSON with a "detail" field, in two shapes:
 *   {"detail": "Wrong email or password."}                                  (HTTPException)
 *   {"detail": [{"loc": ["body", "email"], "msg": "String should ...", ...}]} (422 validation)
 * Pure functions: unit tested in errors.test.ts.
 */

export const BACKEND_UNREACHABLE =
  "Cannot reach the backend. Is FastAPI running (uvicorn on port 8010) and BACKEND_URL correct?";

/** The result of every backend call: either the data, or a status + a readable message. */
export type ApiResult<T> = { ok: true; data: T } | { ok: false; status: number; message: string };

export function messageFromDetail(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const { detail } = payload as { detail: unknown };
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            const loc =
              "loc" in item && Array.isArray(item.loc)
                ? (item.loc as unknown[]).filter((part) => part !== "body").join(".")
                : "";
            return loc ? `${loc}: ${String(item.msg)}` : String(item.msg);
          }
          return String(item);
        })
        .join("; ");
    }
  }
  return fallbackMessage(status);
}

export function fallbackMessage(status: number): string {
  if (status === 0) return BACKEND_UNREACHABLE;
  if (status === 401) return "Your session has ended. Please log in again.";
  if (status === 403) return "You don't have permission to do this.";
  if (status === 404) return "Not found. It may have been deleted.";
  if (status === 429) return "Too many attempts. Please wait a few minutes and try again.";
  if (status >= 500) return "The backend had a problem. Check the FastAPI terminal for the error, then try again.";
  return `The request failed (HTTP ${status}).`;
}
