"use client";

import { useActionState } from "react";

import { FormField } from "@/components/form-field";
import { SubmitButton } from "@/components/submit-button";
import { Alert } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

import { createRole } from "../actions";
import type { FormState } from "../schemas";

/**
 * Add a role (a position to fill) to a project. The DESCRIPTION is what matters most: the AI reads it
 * to extract must-have and nice-to-have skills (Step 7), so write it as you would for a colleague.
 */
export function NewRoleForm({ projectId }: { projectId: number }) {
  const [state, formAction] = useActionState<FormState, FormData>(createRole.bind(null, projectId), {});
  const errors = state.fieldErrors;
  const v = state.values ?? {};
  return (
    <form action={formAction} className="grid gap-4 sm:grid-cols-2" key={JSON.stringify(v)} noValidate>
      {state.message && <Alert className="sm:col-span-2">{state.message}</Alert>}
      <FormField label="Role title" error={errors?.title?.[0]} className="sm:col-span-2">
        <Input
          name="title"
          required
          maxLength={200}
          placeholder="Senior Backend Developer (Django)"
          defaultValue={v.title}
        />
      </FormField>
      <FormField
        label="Description"
        hint="What the person will do and which skills are essential or a plus. The AI turns this into requirements."
        error={errors?.description?.[0]}
        className="sm:col-span-2"
      >
        <Textarea
          name="description"
          rows={6}
          required
          minLength={20}
          placeholder="We need a senior backend developer to rebuild the claims APIs. Must have 5+ years of Python and Django… Nice to have: Celery, Docker."
          defaultValue={v.description}
        />
      </FormField>
      <FormField label="Location" hint="Empty = anywhere, or what the description says" error={errors?.location?.[0]}>
        <Input name="location" maxLength={100} defaultValue={v.location} />
      </FormField>
      <FormField label="Start date" error={errors?.start_date?.[0]}>
        <Input name="start_date" type="date" defaultValue={v.start_date} />
      </FormField>
      <div className="grid grid-cols-3 gap-4 sm:col-span-2">
        <FormField label="Allocation %" error={errors?.allocation_percent?.[0]}>
          <Input
            name="allocation_percent"
            type="number"
            min={1}
            max={100}
            defaultValue={v.allocation_percent ?? "100"}
          />
        </FormField>
        <FormField label="Headcount" error={errors?.headcount?.[0]}>
          <Input name="headcount" type="number" min={1} max={50} defaultValue={v.headcount ?? "1"} />
        </FormField>
        <FormField label="Min. years" hint="Optional" error={errors?.min_experience_years?.[0]}>
          <Input
            name="min_experience_years"
            type="number"
            min={0}
            max={50}
            step={0.5}
            defaultValue={v.min_experience_years}
          />
        </FormField>
      </div>
      <div className="sm:col-span-2">
        <SubmitButton pendingLabel="Adding…">Add role</SubmitButton>
      </div>
    </form>
  );
}
