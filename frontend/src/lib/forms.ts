/**
 * Shared shapes for forms that post to Server Actions (used by every feature).
 *
 * The action returns a FormState: a message for the whole form, messages per field, the values to
 * put back after an error (React resets a form after its action runs), and ok=true on success.
 */
export type FormState = {
  message?: string;
  fieldErrors?: Record<string, string[] | undefined>;
  values?: Record<string, string>;
  ok?: boolean;
};

/** FormData -> plain object of strings (files ignored), for zod and for re-filling a form after an error. */
export function formValues(formData: FormData): Record<string, string> {
  const values: Record<string, string> = {};
  for (const [key, value] of formData.entries()) if (typeof value === "string") values[key] = value;
  return values;
}
