"use client";

import { useActionState } from "react";

import { FormField } from "@/components/form-field";
import { SubmitButton } from "@/components/submit-button";
import { Alert } from "@/components/ui/alert";
import type { FormState } from "@/lib/forms";

import { changeOwnPassword } from "../actions";
import { MIN_PASSWORD_LENGTH } from "../schemas";
import { PasswordInput } from "./password-field";

/** Change your own password: the current one proves it's you, the new one is typed twice. */
export function ChangePasswordForm() {
  const [state, formAction] = useActionState<FormState, FormData>(changeOwnPassword, {});
  const errors = state.fieldErrors;
  return (
    <form action={formAction} className="max-w-sm space-y-4" key={JSON.stringify(state)} noValidate>
      {state.message && <Alert tone={state.ok ? "info" : "danger"}>{state.message}</Alert>}
      <FormField label="Current password" error={errors?.current_password?.[0]}>
        <PasswordInput name="current_password" autoComplete="current-password" />
      </FormField>
      <FormField
        label="New password"
        hint={`At least ${MIN_PASSWORD_LENGTH} characters. A short sentence is easy to remember and hard to guess.`}
        error={errors?.new_password?.[0]}
      >
        <PasswordInput name="new_password" autoComplete="new-password" />
      </FormField>
      <FormField label="New password again" error={errors?.confirm_password?.[0]}>
        <PasswordInput name="confirm_password" autoComplete="new-password" />
      </FormField>
      <SubmitButton pendingLabel="Changing…">Change password</SubmitButton>
    </form>
  );
}
