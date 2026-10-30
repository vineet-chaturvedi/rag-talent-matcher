import { z } from "zod";

/**
 * The shape of the frontend's settings (environment variables), checked with zod.
 *
 * Why: `process.env.X` is always `string | undefined`. A typo in `.env.local` ("BACKEND_ULR") or a bad
 * value ("localhost:8010" without http://) would otherwise surface much later as a confusing network
 * error. Parsing once at startup turns it into a clear message that names the variable.
 *
 * This file has no "server-only" marker so that `next.config.ts` can import it too.
 * Application code imports `env` from `@/lib/env` instead, which IS server-only.
 */

/** "true"/"1"/"yes" -> true; anything else (or unset) -> the default. Env values are always strings. */
const booleanFlag = (fallback: boolean) =>
  z
    .string()
    .optional()
    .transform((v) => (v === undefined || v === "" ? fallback : ["true", "1", "yes"].includes(v.toLowerCase())));

export const envSchema = z.object({
  /** Where FastAPI runs. Only the Next.js server talks to it; the browser never sees this address. */
  BACKEND_URL: z
    // protocol: "localhost:8010" alone is a valid URL with the scheme "localhost:", so insist on http(s).
    .url({ protocol: /^https?$/, error: "BACKEND_URL must be a full URL such as http://127.0.0.1:8010" })
    .default("http://127.0.0.1:8010")
    .transform((u) => u.replace(/\/+$/, "")), // no trailing slash: we append "/api/..."

  /**
   * Set to true when the portal is served over HTTPS (production behind TLS). It turns on
   * Secure cookies (never sent over plain HTTP), HSTS and `upgrade-insecure-requests`.
   * Leave it false for http://localhost, or the browser would drop the login cookie on a LAN IP.
   */
  HTTPS: booleanFlag(false),

  NODE_ENV: z.enum(["development", "production", "test"]).default("development"),
});

export type Env = z.infer<typeof envSchema>;

/** Parse, or stop with a readable list of problems (one line per bad variable). */
export function parseEnv(source: Record<string, string | undefined>): Env {
  const result = envSchema.safeParse(source);
  if (!result.success) {
    const problems = result.error.issues.map((i) => `  - ${i.path.join(".")}: ${i.message}`).join("\n");
    throw new Error(`Invalid frontend settings (.env.local):\n${problems}`);
  }
  return result.data;
}
