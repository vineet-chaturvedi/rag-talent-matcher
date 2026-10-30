import { z } from "zod";

import { SENIORITY } from "./labels";

/**
 * What the Step 12b forms may send, checked on the server before anything reaches FastAPI.
 * The limits mirror the backend's Pydantic models (ProjectCreate, RoleCreate, Requirements,
 * MatchRequest), so a person gets a clear message here instead of a 422 from the API.
 * Pure: unit tested in schemas.test.ts.
 */

const optionalText = (max: number) =>
  z
    .string()
    .trim()
    .max(max, { error: `At most ${max} characters.` })
    .transform((v) => (v === "" ? null : v))
    .nullable()
    .default(null);

/** <input type="date"> sends "" when empty and "2026-12-01" otherwise. */
const optionalDate = z
  .string()
  .trim()
  .transform((v) => (v === "" ? null : v))
  .pipe(z.iso.date({ error: "Use a date like 2026-12-01." }).nullable())
  .nullable()
  .default(null);

/** <input type="number"> sends "" when empty. */
const optionalNumber = (min: number, max: number) =>
  z
    .string()
    .trim()
    .transform((v) => (v === "" ? null : Number(v)))
    .pipe(z.number({ error: "Enter a number." }).min(min).max(max).nullable())
    .nullable()
    .default(null);

/**
 * A whole number with a default. Careful: z.coerce.number() turns "" (an emptied field) into 0, which
 * would fail "min 1" instead of using the default. So "" becomes undefined first, and the default applies.
 * (Found by schemas.test.ts.)
 */
const intWithDefault = (min: number, max: number, fallback: number) =>
  z.preprocess(
    (v) => (v === "" || v === null ? undefined : v),
    z.coerce.number().int().min(min).max(max).default(fallback),
  );

export const projectSchema = z.object({
  name: z.string().trim().min(2, { error: "Give the project a name (2 characters or more)." }).max(200),
  client_name: optionalText(200),
  description: optionalText(5000),
  status: z.enum(["planned", "active", "on_hold", "completed"]).default("planned"),
  start_date: optionalDate,
  end_date: optionalDate,
});

export const roleSchema = z.object({
  title: z.string().trim().min(2, { error: "Give the role a title." }).max(200),
  description: z
    .string()
    .trim()
    .min(20, { error: "Describe the role in at least a sentence (20 characters): the AI reads this text." }),
  location: optionalText(100),
  allocation_percent: intWithDefault(1, 100, 100),
  start_date: optionalDate,
  headcount: intWithDefault(1, 50, 1),
  min_experience_years: optionalNumber(0, 50),
});

const skillSchema = z.object({
  name: z.string().trim().min(1).max(100),
  min_years: z.number().min(0).max(50).nullable().default(null),
});

/** The requirements editor sends its whole state as one JSON field ("payload"). */
export const requirementsSchema = z.object({
  seniority: z.enum(SENIORITY).default("unspecified"),
  must_have: z.array(skillSchema).max(30),
  nice_to_have: z.array(skillSchema).max(30),
  min_total_years: z.number().min(0).max(50).nullable().default(null),
  location: z.string().trim().max(100).nullable().default(null),
  domain: z.array(z.string().trim().min(1).max(60)).max(10).default([]),
  search_summary: z.string().trim().max(2000).default(""),
});

export type RequirementsInput = z.infer<typeof requirementsSchema>;

export const matchSchema = z.object({
  top_k: intWithDefault(1, 50, 10),
  judge_top_n: intWithDefault(0, 20, 5),
  only_available: z
    .union([z.literal("on"), z.literal("")])
    .optional()
    .transform((v) => v === "on"),
});

/** Shared with every feature; re-exported here so existing imports keep working. */
export { type FormState, formValues } from "@/lib/forms";
