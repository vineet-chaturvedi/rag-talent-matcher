"use client";

import { LoaderCircle } from "lucide-react";
import { useActionState, useRef } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button, type ButtonProps } from "@/components/ui/button";
import type { ActionResult } from "@/lib/actions";
import { cn } from "@/lib/utils";

type Confirm = { title: string; description: string; confirmLabel: string };

/**
 * A button that runs ONE Server Action and shows its result next to it.
 *
 *   <ActionButton action={retryResume.bind(null, resume.id)} label="Retry" pendingLabel="Retrying…" />
 *
 * - `action.bind(null, id)` creates a Server Action with the id already filled in. Next.js encrypts
 *   bound values, so the browser can't swap the id; the backend still checks permissions anyway.
 * - It's a real <form>: the button works as soon as the HTML arrives.
 * - With `confirm`, a dialog asks first, and its button submits the form with `requestSubmit()`.
 *   Why not a submit button: the dialog is rendered in a portal (outside the form), and Radix closes
 *   it on click, removing the button from the page BEFORE the browser runs the submit, so nothing
 *   was sent. Found by the Step 12 browser test; the account menu's "Sign out" had the same bug.
 */
export function ActionButton({
  action,
  label,
  pendingLabel,
  confirm,
  variant = "outline",
  size = "sm",
  className,
}: {
  action: () => Promise<ActionResult>;
  label: string;
  pendingLabel: string;
  confirm?: Confirm;
  variant?: ButtonProps["variant"];
  size?: ButtonProps["size"];
  className?: string;
}) {
  const [result, formAction, pending] = useActionState(async () => action(), null);
  const formRef = useRef<HTMLFormElement>(null);

  const content = pending ? (
    <>
      <LoaderCircle className="animate-spin" aria-hidden /> {pendingLabel}
    </>
  ) : (
    label
  );

  return (
    <div className={cn("inline-flex flex-wrap items-center gap-2", className)}>
      <form ref={formRef} action={formAction}>
        {!confirm && (
          <Button type="submit" variant={variant} size={size} disabled={pending}>
            {content}
          </Button>
        )}
      </form>
      {confirm && (
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button type="button" variant={variant} size={size} disabled={pending}>
              {content}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogTitle>{confirm.title}</AlertDialogTitle>
            <AlertDialogDescription>{confirm.description}</AlertDialogDescription>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={() => formRef.current?.requestSubmit()}>
                {confirm.confirmLabel}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}
      {result && (
        <span role="status" className={cn("text-xs", result.ok ? "text-success" : "text-destructive")}>
          {result.message}
        </span>
      )}
    </div>
  );
}
