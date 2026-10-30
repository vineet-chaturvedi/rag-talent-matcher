"use client";

import { useActionState } from "react";

import { FormField } from "@/components/form-field";
import { SubmitButton } from "@/components/submit-button";
import { Alert } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import type { FormState } from "@/lib/forms";

import { createUser } from "../actions";
import { MIN_PASSWORD_LENGTH, ROLE_LABEL } from "../schemas";
import { PasswordInput } from "./password-field";

/** Create a portal account. The admin sets a first password and gives it to the person directly. */
export function NewUserForm() {
  const [state, formAction] = useActionState<FormState, FormData>(createUser, {});
  const errors = state.fieldErrors;
  const v = state.ok ? {} : (state.values ?? {});
  return (
    <form action={formAction} className="grid gap-4 sm:grid-cols-2" key={JSON.stringify(state)} noValidate>
      {state.message && (
        <Alert tone={state.ok ? "info" : "danger"} className="sm:col-span-2">
          {state.message}
        </Alert>
      )}
      <FormField label="Full name" error={errors?.full_name?.[0]}>
        <Input name="full_name" autoComplete="off" maxLength={200} defaultValue={v.full_name} />
      </FormField>
      <FormField label="Email" error={errors?.email?.[0]}>
        <Input name="email" type="email" autoComplete="off" defaultValue={v.email} />
      </FormField>
      <FormField
        label="Role"
        hint="Resource managers find people and run matches; administrators also manage resumes and users."
        error={errors?.role?.[0]}
      >
        <NativeSelect name="role" defaultValue={v.role ?? "resource_manager"}>
          <option value="resource_manager">{ROLE_LABEL.resource_manager}</option>
          <option value="admin">{ROLE_LABEL.admin}</option>
        </NativeSelect>
      </FormField>
      <FormField
        label="First password"
        hint={`At least ${MIN_PASSWORD_LENGTH} characters. They can change it on their Account page.`}
        error={errors?.password?.[0]}
      >
        <PasswordInput name="password" autoComplete="new-password" />
      </FormField>
      <div className="sm:col-span-2">
        <SubmitButton pendingLabel="Creating…">Create account</SubmitButton>
      </div>
    </form>
  );
}
