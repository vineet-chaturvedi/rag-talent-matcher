import { z } from "zod";

/**
 * Reading values from the URL (?page=2&status=failed) safely.
 *
 * The URL is typed by people and crafted by anyone, so every value is untrusted: "?page=-5",
 * "?page=abc", "?status=<script>". These helpers turn whatever arrives into a valid value or a
 * default, so a bad link shows page 1 instead of an error. Pure functions: unit tested.
 */

type Raw = string | string[] | undefined;

/** The first value if a parameter was given twice (?page=1&page=2). */
const first = (value: Raw) => (Array.isArray(value) ? value[0] : value);

const pageSchema = z.coerce.number().int().min(1).max(10_000);

export function pageParam(value: Raw): number {
  const parsed = pageSchema.safeParse(first(value));
  return parsed.success ? parsed.data : 1;
}

/** A value from a fixed list (an enum), else undefined (= "no filter"). */
export function enumParam<T extends string>(value: Raw, allowed: readonly T[]): T | undefined {
  const v = first(value);
  return v !== undefined && (allowed as readonly string[]).includes(v) ? (v as T) : undefined;
}

/** Free text such as a search box: trimmed, at most `max` characters, empty -> undefined. */
export function textParam(value: Raw, max = 100): string | undefined {
  const v = first(value)?.trim().slice(0, max);
  return v ? v : undefined;
}

/** A positive integer id from a dynamic route segment (/employees/[id]), else null (-> 404). */
export function idParam(value: Raw): number | null {
  const parsed = z.coerce.number().int().positive().safeParse(first(value));
  return parsed.success ? parsed.data : null;
}
