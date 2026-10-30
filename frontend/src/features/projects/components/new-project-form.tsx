"use client";

import { useActionState } from "react";

import { FormField } from "@/components/form-field";
import { SubmitButton } from "@/components/submit-button";
import { Alert } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";

import { createProject } from "../actions";
import { PROJECT_STATUS } from "../labels";
import type { FormState } from "../schemas";

/** Create a project. On success the Server Action redirects to the new project's page. */
export function NewProjectForm() {
  const [state, formAction] = useActionState<FormState, FormData>(createProject, {});
  const errors = state.fieldErrors;
  const v = state.values ?? {};
  return (
    // key: after a failed attempt React resets the form; remounting with the returned values refills it.
    <form action={formAction} className="grid gap-4 sm:grid-cols-2" key={JSON.stringify(v)} noValidate>
      {state.message && <Alert className="sm:col-span-2">{state.message}</Alert>}
      <FormField label="Project name" error={errors?.name?.[0]}>
        <Input name="name" required maxLength={200} defaultValue={v.name} />
      </FormField>
      <FormField label="Client" hint="Optional" error={errors?.client_name?.[0]}>
        <Input name="client_name" maxLength={200} defaultValue={v.client_name} />
      </FormField>
      <FormField label="Status" error={errors?.status?.[0]}>
        <NativeSelect name="status" defaultValue={v.status ?? "planned"}>
          {PROJECT_STATUS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </NativeSelect>
      </FormField>
      <div className="grid grid-cols-2 gap-4">
        <FormField label="Start" error={errors?.start_date?.[0]}>
          <Input name="start_date" type="date" defaultValue={v.start_date} />
        </FormField>
        <FormField label="End" error={errors?.end_date?.[0]}>
          <Input name="end_date" type="date" defaultValue={v.end_date} />
        </FormField>
      </div>
      <FormField label="Description" hint="Optional" error={errors?.description?.[0]} className="sm:col-span-2">
        <Textarea name="description" rows={3} defaultValue={v.description} />
      </FormField>
      <div className="sm:col-span-2">
        <SubmitButton pendingLabel="Creating…">Create project</SubmitButton>
      </div>
    </form>
  );
}
