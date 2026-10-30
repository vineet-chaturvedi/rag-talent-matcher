"use client";

import { useActionState } from "react";

import { FormField } from "@/components/form-field";
import { SubmitButton } from "@/components/submit-button";
import { Alert } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";

import { startMatch } from "../actions";
import type { FormState } from "../schemas";

/**
 * Start a match run. Retrieval and rule scoring take about a second; the LLM judge then reads the
 * top N resumes one by one (about a minute each with the 7B model on a CPU), in the background.
 */
export function MatchForm({ roleId }: { roleId: number }) {
  const [state, formAction] = useActionState<FormState, FormData>(startMatch.bind(null, roleId), {});
  const errors = state.fieldErrors;
  const v = state.values ?? {};
  return (
    <form action={formAction} className="space-y-4" key={JSON.stringify(v)} noValidate>
      {state.message && <Alert>{state.message}</Alert>}
      <div className="grid grid-cols-2 gap-4">
        <FormField label="Candidates" hint="How many to rank (1-50)" error={errors?.top_k?.[0]}>
          <Input name="top_k" type="number" min={1} max={50} defaultValue={v.top_k ?? "10"} />
        </FormField>
        <FormField label="AI judge reads" hint="Top N resumes; 0 = rules only" error={errors?.judge_top_n?.[0]}>
          <Input name="judge_top_n" type="number" min={0} max={20} defaultValue={v.judge_top_n ?? "5"} />
        </FormField>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          name="only_available"
          defaultChecked={v.only_available === "on"}
          className="size-4 accent-primary"
        />
        Only people who can take the role&apos;s allocation by its start date
      </label>
      <SubmitButton pendingLabel="Ranking…">Find best matches</SubmitButton>
      <p className="text-xs text-muted-foreground">
        The ranking appears at once; the judge&apos;s verdicts follow at about a minute per resume.
      </p>
    </form>
  );
}
