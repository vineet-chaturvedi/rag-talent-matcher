import type { AgentMessage, MyFeedback } from "@/lib/api/types";

/**
 * One question and everything the agent did for it: the tool steps, then the answer.
 * The chat shows TURNS, not raw messages; both the live stream and a stored conversation are
 * turned into this one shape, so they look exactly the same.
 */
export type Step = {
  name: string;
  arguments: Record<string, unknown>;
  status: "running" | "ok" | "failed";
  summary?: string;
};

export type Turn = {
  id: string;
  question: string;
  steps: Step[];
  answer: string;
  status: "streaming" | "done" | "error" | "stopped";
  error?: string;
  seconds?: number;
  /** The saved answer message (for 👍 / 👎) and my rating of it (Step 14c). */
  messageId?: number;
  feedback?: MyFeedback | null;
};

/**
 * Stored messages (user / assistant with tool_calls / tool / assistant answer, in order) -> turns.
 * Pure: no React, no network.
 */
export function messagesToTurns(messages: readonly AgentMessage[]): Turn[] {
  const turns: Turn[] = [];
  let current: Turn | null = null;
  for (const m of messages) {
    if (m.role === "user") {
      current = { id: `m${m.id}`, question: m.content, steps: [], answer: "", status: "done" };
      turns.push(current);
      continue;
    }
    if (!current) continue; // messages before any question: nothing to attach them to
    if (m.role === "assistant" && Array.isArray(m.tool_calls) && m.tool_calls.length > 0) {
      for (const call of m.tool_calls as { name?: string; arguments?: Record<string, unknown> }[]) {
        current.steps.push({ name: call.name ?? "tool", arguments: call.arguments ?? {}, status: "running" });
      }
    } else if (m.role === "tool") {
      const step = current.steps.find((s) => s.status === "running" && s.name === m.tool_name);
      if (step) {
        step.status = m.summary?.startsWith("error") ? "failed" : "ok";
        step.summary = m.summary ?? undefined;
      }
    } else if (m.role === "assistant") {
      current.answer = m.content;
      current.messageId = m.id;
      current.feedback = m.feedback ?? null;
    }
  }
  // A question without a saved answer: the stream was interrupted (page closed, server restarted).
  for (const turn of turns) {
    for (const step of turn.steps) if (step.status === "running") step.status = "failed";
    if (!turn.answer) {
      turn.status = "stopped";
      turn.error = "This answer was interrupted before it finished.";
    }
  }
  return turns;
}

/** The arguments of a tool call as a short line: "must_have: Kubernetes, AWS · start_date: 2026-12-01". */
export function describeArguments(args: Record<string, unknown>): string {
  return Object.entries(args)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : String(value)}`)
    .join(" · ");
}

/** Employee codes in an answer become links to the employee list, searched for that code. */
export function linkEmployeeCodes(markdown: string): string {
  return markdown.replace(/(?<![\[\w/-])(EMP-\d{3,6})(?![\w\]])/g, "[$1](/employees?q=$1)");
}
