import { z } from "zod";

/**
 * Portal accounts (Step 12c): what the forms may send, checked on the server before FastAPI.
 * The password rule mirrors the backend (app/auth/passwords.py, NIST SP 800-63B): LONG beats
 * complicated, so at least 12 characters and no forced mix of symbols; no leading/trailing spaces
 * (they are invisible and get lost when people copy a password).
 */
export const MIN_PASSWORD_LENGTH = 12; // = backend MIN_PASSWORD_LENGTH

const password = z
  .string()
  .min(MIN_PASSWORD_LENGTH, { error: `At least ${MIN_PASSWORD_LENGTH} characters. A short sentence works well.` })
  .max(200, { error: "At most 200 characters." })
  .refine((v) => v.trim() === v, { error: "No spaces at the start or end." });

export const createUserSchema = z.object({
  full_name: z.string().trim().min(2, { error: "Enter the person's name." }).max(200),
  email: z
    .string()
    .trim()
    .toLowerCase()
    .pipe(z.email({ error: "That doesn't look like an email address." })),
  role: z.enum(["admin", "resource_manager"], { error: "Choose a role." }),
  password,
});

export const resetPasswordSchema = z.object({ password });

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, { error: "Enter your current password." }),
    new_password: password,
    confirm_password: z.string(),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    path: ["confirm_password"],
    error: "The two new passwords are not the same.",
  })
  .refine((v) => v.new_password !== v.current_password, {
    path: ["new_password"],
    error: "Choose a password different from the current one.",
  });

export const ROLE_LABEL = { admin: "Administrator", resource_manager: "Resource manager" } as const;
