import { z } from "zod";

/**
 * What the login form must contain, checked on the SERVER (in the Server Action).
 *
 * The browser also checks (type="email", required), but that is only for comfort: anyone can send a
 * POST without the form, so the server validates again before calling FastAPI. FastAPI then checks a
 * third time. Each layer protects the next one from garbage.
 */
export const loginSchema = z.object({
  email: z
    .string({ error: "Enter your email address." })
    .trim()
    .toLowerCase()
    .min(1, { error: "Enter your email address." })
    .pipe(z.email({ error: "That doesn't look like an email address." })),
  password: z
    .string({ error: "Enter your password." })
    .min(1, { error: "Enter your password." })
    .max(200, { error: "That password is too long." }),
});

export type LoginInput = z.infer<typeof loginSchema>;

/** What the Server Action sends back to the form after a failed attempt (success = a redirect). */
export type LoginState = {
  /** A message for the whole form, e.g. "Wrong email or password." */
  message?: string;
  /** Messages for single fields, e.g. { email: ["That doesn't look like an email address."] } */
  fieldErrors?: Partial<Record<keyof LoginInput, string[]>>;
  /** The email typed, so the form can show it again (passwords are never sent back). */
  email?: string;
};
