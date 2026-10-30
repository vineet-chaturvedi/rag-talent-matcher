"use client";

import { KeyRound } from "lucide-react";
import { useActionState } from "react";

import { FormField } from "@/components/form-field";
import { SubmitButton } from "@/components/submit-button";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import type { FormState } from "@/lib/forms";

import { resetPassword } from "../actions";
import { MIN_PASSWORD_LENGTH } from "../schemas";
import { PasswordInput } from "./password-field";

/**
 * An admin sets a new password for someone who forgot theirs. The form lives INSIDE the dialog
 * (button and form in the same portal), so a normal submit works here.
 */
export function ResetPasswordDialog({ userId, name }: { userId: number; name: string }) {
  const [state, formAction] = useActionState<FormState, FormData>(resetPassword.bind(null, userId), {});
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm">
          <KeyRound aria-hidden /> Reset password
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>New password for {name}</DialogTitle>
        <DialogDescription>
          Give it to them in person or by phone. They can change it themselves on their Account page.
        </DialogDescription>
        <form action={formAction} className="space-y-4" noValidate key={state.ok ? "done" : "form"}>
          {state.message && <Alert tone={state.ok ? "info" : "danger"}>{state.message}</Alert>}
          {!state.ok && (
            <>
              <FormField
                label="New password"
                hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
                error={state.fieldErrors?.password?.[0]}
              >
                <PasswordInput name="password" autoComplete="new-password" />
              </FormField>
              <SubmitButton pendingLabel="Saving…">Set password</SubmitButton>
            </>
          )}
        </form>
      </DialogContent>
    </Dialog>
  );
}
