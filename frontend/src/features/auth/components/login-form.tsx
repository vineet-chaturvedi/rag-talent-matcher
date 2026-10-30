"use client";

import { LoaderCircle } from "lucide-react";
import { useActionState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import type { LoginState } from "../schemas";

type LoginAction = (state: LoginState, formData: FormData) => Promise<LoginState>;

/**
 * The login form.
 *
 * `useActionState(action, initialState)` (React 19) connects a <form> to a Server Action:
 *   - `formAction` goes into <form action>; submitting POSTs the fields to the server.
 *   - `state` is whatever the action returned last time (an error message, field errors).
 *   - `pending` is true while the server is working: the button shows a spinner and is disabled.
 * Success is a redirect done by the server, so the form never needs a "success" state.
 *
 * The action comes in as a prop (from the server page) rather than being imported here. That keeps
 * this component easy to test: a test passes a fake action, no server needed.
 */
export function LoginForm({ action, notice }: { action: LoginAction; notice?: React.ReactNode }) {
  const [state, formAction, pending] = useActionState(action, {});
  const emailError = state.fieldErrors?.email?.[0];
  const passwordError = state.fieldErrors?.password?.[0];

  return (
    <form action={formAction} className="space-y-4" noValidate>
      {state.message ? <Alert>{state.message}</Alert> : notice}

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          required
          autoFocus
          // React 19 resets a form after its action runs; keep what was typed so a typo is easy to fix.
          defaultValue={state.email}
          key={state.email}
          aria-invalid={emailError ? true : undefined}
          aria-describedby={emailError ? "email-error" : undefined}
        />
        {emailError && (
          <p id="email-error" className="text-sm text-destructive">
            {emailError}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          aria-invalid={passwordError ? true : undefined}
          aria-describedby={passwordError ? "password-error" : undefined}
        />
        {passwordError && (
          <p id="password-error" className="text-sm text-destructive">
            {passwordError}
          </p>
        )}
      </div>

      <Button type="submit" className="w-full" disabled={pending}>
        {pending && <LoaderCircle className="animate-spin" aria-hidden />}
        {pending ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
