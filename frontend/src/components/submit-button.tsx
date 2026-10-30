"use client";

import { LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";
import { useFormStatus } from "react-dom";

import { Button, type ButtonProps } from "@/components/ui/button";

/**
 * A form's submit button that knows whether ITS form is being submitted (React's useFormStatus),
 * so it can show a spinner and block double submits without any state in the form itself.
 */
export function SubmitButton({
  children,
  pendingLabel,
  ...props
}: ButtonProps & { pendingLabel: string; children: ReactNode }) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" disabled={pending || props.disabled} {...props}>
      {pending && <LoaderCircle className="animate-spin" aria-hidden />}
      {pending ? pendingLabel : children}
    </Button>
  );
}
