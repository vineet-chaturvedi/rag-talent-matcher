"use client";

import { LoaderCircle, ThumbsDown, ThumbsUp } from "lucide-react";
import { useId, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import type { MyFeedback } from "@/lib/api/types";
import { cn } from "@/lib/utils";

import {
  clearAgentFeedback,
  clearMatchFeedback,
  type FeedbackInput,
  type FeedbackResult,
  rateAgentAnswer,
  rateMatchResult,
} from "../actions";
import { AGENT_REASONS, MATCH_REASONS, reasonLabel } from "../labels";

type Target = "match" | "agent";

const ACTIONS: Record<
  Target,
  {
    rate: (id: number, input: FeedbackInput) => Promise<FeedbackResult>;
    clear: (id: number) => Promise<FeedbackResult>;
  }
> = {
  match: { rate: rateMatchResult, clear: clearMatchFeedback },
  agent: { rate: rateAgentAnswer, clear: clearAgentFeedback },
};

const QUESTION: Record<Target, { up: string; down: string; prompt: string }> = {
  match: { up: "Good match", down: "Not a good match", prompt: "What's wrong with this match?" },
  agent: { up: "Helpful answer", down: "Wrong or unhelpful answer", prompt: "What was wrong with the answer?" },
};

/**
 * 👍 / 👎 on one match result or one agent answer (Step 14c). Every click is a labelled example for
 * evaluation and tuning (doc 19).
 *   - A thumb saves at once; pressing the same thumb again takes the rating back.
 *   - After 👎 a short form asks why (a fixed list, so reasons can be counted) and for an optional note.
 *   - The state lives here (useState): no page refresh, so a long results page doesn't jump.
 *   - useTransition keeps the buttons responsive and shows a spinner while the Server Action runs.
 */
export function FeedbackButtons({
  target,
  id,
  initial,
  className,
}: {
  target: Target;
  id: number;
  initial: MyFeedback | null | undefined;
  className?: string;
}) {
  const [feedback, setFeedback] = useState<MyFeedback | null>(initial ?? null);
  const [asking, setAsking] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const formId = useId();
  const reasons = target === "match" ? MATCH_REASONS : AGENT_REASONS;
  const text = QUESTION[target];

  function run(call: () => Promise<FeedbackResult>, done: string, after?: (fb: MyFeedback | null) => void) {
    startTransition(async () => {
      const result = await call();
      if (result.ok) {
        setFeedback(result.feedback);
        setMessage(done);
        after?.(result.feedback);
      } else {
        setMessage(result.message);
      }
    });
  }

  function press(rating: "up" | "down") {
    if (feedback?.rating === rating) {
      run(
        () => ACTIONS[target].clear(id),
        "Rating removed.",
        () => setAsking(false),
      );
      return;
    }
    run(
      () => ACTIONS[target].rate(id, { rating }),
      rating === "up" ? "Thanks, saved." : "Saved. Tell us why?",
      () => setAsking(rating === "down"),
    );
  }

  function saveReason(form: FormData) {
    const reason = String(form.get("reason") || "") || undefined;
    const comment = String(form.get("comment") || "").trim() || undefined;
    run(
      () => ACTIONS[target].rate(id, { rating: "down", reason, comment }),
      "Thanks, saved.",
      () => setAsking(false),
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs text-muted-foreground">Was this right?</span>
        <Thumb pressed={feedback?.rating === "up"} label={text.up} disabled={pending} onClick={() => press("up")}>
          <ThumbsUp aria-hidden />
        </Thumb>
        <Thumb pressed={feedback?.rating === "down"} label={text.down} disabled={pending} onClick={() => press("down")}>
          <ThumbsDown aria-hidden />
        </Thumb>
        {pending && <LoaderCircle className="size-3.5 animate-spin text-muted-foreground" aria-label="Saving" />}
        {feedback?.rating === "down" && feedback.reason && !asking && (
          <span className="text-xs text-muted-foreground">· {reasonLabel(feedback.reason)}</span>
        )}
        {feedback?.rating === "down" && !asking && (
          <button type="button" className="text-xs text-primary hover:underline" onClick={() => setAsking(true)}>
            {feedback.reason ? "change" : "add a reason"}
          </button>
        )}
        <span className="text-xs text-muted-foreground" role="status" aria-live="polite">
          {message}
        </span>
      </div>

      {asking && (
        <form action={saveReason} className="grid gap-2 rounded-md border bg-muted/40 p-3 sm:max-w-md">
          <label htmlFor={`${formId}-reason`} className="text-xs font-medium">
            {text.prompt}
          </label>
          <NativeSelect id={`${formId}-reason`} name="reason" defaultValue={feedback?.reason ?? ""}>
            <option value="">Choose a reason (optional)</option>
            {reasons.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </NativeSelect>
          <label htmlFor={`${formId}-comment`} className="sr-only">
            A note (optional)
          </label>
          <Textarea
            id={`${formId}-comment`}
            name="comment"
            maxLength={1000}
            defaultValue={feedback?.comment ?? ""}
            placeholder="A note (optional), e.g. who should be here instead"
            className="min-h-16"
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={pending}>
              Save
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setAsking(false)}>
              Skip
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

function Thumb({
  pressed,
  label,
  disabled,
  onClick,
  children,
}: {
  pressed: boolean;
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant={pressed ? "secondary" : "ghost"}
      aria-pressed={pressed}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className={cn("h-7 px-2", pressed && "text-primary ring-1 ring-primary/40")}
    >
      {children}
    </Button>
  );
}
