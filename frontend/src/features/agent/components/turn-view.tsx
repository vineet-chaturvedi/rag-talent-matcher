import { CircleCheck, CircleX, LoaderCircle, Wrench } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

import { toolLabel } from "../events";
import { describeArguments, type Turn } from "../transcript";
import { Markdown } from "./markdown";

/**
 * One turn: the question, what the agent did (each tool call, live), and the answer.
 * Showing the steps is deliberate: the person sees WHICH data the answer is based on ("Searching for
 * matching people: must_have Kubernetes, AWS → 5 found"), and can judge it, instead of trusting
 * a fluent paragraph.
 */
export function TurnView({ turn }: { turn: Turn }) {
  const streaming = turn.status === "streaming";
  return (
    <article className="space-y-3" aria-busy={streaming}>
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm whitespace-pre-wrap text-primary-foreground">
          {turn.question}
        </p>
      </div>

      <div className="max-w-[92%] space-y-3 rounded-2xl rounded-bl-sm border bg-card px-4 py-3 shadow-xs">
        {turn.steps.length > 0 && (
          <ol className="space-y-1.5 border-b pb-3" aria-label="What the assistant did">
            {turn.steps.map((step, index) => (
              <li key={index} className="flex items-start gap-2 text-xs">
                <StepIcon status={step.status === "running" && !streaming ? "interrupted" : step.status} />
                <div className="min-w-0">
                  <span className="font-medium">{toolLabel(step.name)}</span>
                  {Object.keys(step.arguments).length > 0 && (
                    <span className="text-muted-foreground"> · {describeArguments(step.arguments)}</span>
                  )}
                  {step.summary && (
                    <span
                      className={cn("block", step.status === "failed" ? "text-destructive" : "text-muted-foreground")}
                    >
                      → {step.summary}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}

        {turn.answer ? (
          <div className="relative">
            <Markdown text={turn.answer} />
            {streaming && (
              <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-primary align-middle" aria-hidden />
            )}
          </div>
        ) : (
          streaming && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <LoaderCircle className="size-4 animate-spin" aria-hidden />
              {turn.steps.length ? "Thinking about the results…" : "Thinking…"}
            </p>
          )
        )}

        {turn.status === "error" && <Alert title="The assistant could not answer">{turn.error}</Alert>}
        {turn.status === "stopped" && (
          <p className="text-xs text-muted-foreground">{turn.error ?? "Stopped. Ask again to get a full answer."}</p>
        )}
        {turn.status === "done" && turn.seconds !== undefined && (
          <p className="text-xs text-muted-foreground">
            {turn.steps.length} {turn.steps.length === 1 ? "step" : "steps"} · {turn.seconds} s
          </p>
        )}
      </div>
    </article>
  );
}

/** "interrupted": the turn ended (stopped, error) while this tool was still running. */
function StepIcon({ status }: { status: Turn["steps"][number]["status"] | "interrupted" }) {
  if (status === "running")
    return <LoaderCircle className="mt-0.5 size-3.5 shrink-0 animate-spin text-primary" aria-label="Working" />;
  if (status === "failed") return <CircleX className="mt-0.5 size-3.5 shrink-0 text-destructive" aria-label="Failed" />;
  if (status === "ok") return <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-success" aria-label="Done" />;
  return <Wrench className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-label="Not finished" />;
}
