"use server";

import { z } from "zod";

import { request } from "@/lib/api/client";
import type { AgentFeedbackReason, MatchFeedbackReason, MyFeedback } from "@/lib/api/types";

import { AGENT_REASONS, MATCH_REASONS } from "./labels";

/**
 * Feedback Server Actions (Step 14c). Any signed-in user may rate; FastAPI checks the session, and for
 * agent answers that the answer is in the person's OWN conversation. Nothing is refreshed: the buttons
 * keep their own state, so a long match page doesn't re-render on every click.
 */
export type FeedbackResult = { ok: true; feedback: MyFeedback | null } | { ok: false; message: string };

const id = z.number().int().positive();
const comment = z.string().trim().max(1000).optional();
const MATCH_VALUES = MATCH_REASONS.map((r) => r.value) as [MatchFeedbackReason, ...MatchFeedbackReason[]];
const AGENT_VALUES = AGENT_REASONS.map((r) => r.value) as [AgentFeedbackReason, ...AgentFeedbackReason[]];
const matchInput = z.object({ rating: z.enum(["up", "down"]), reason: z.enum(MATCH_VALUES).optional(), comment });
const agentInput = z.object({ rating: z.enum(["up", "down"]), reason: z.enum(AGENT_VALUES).optional(), comment });

/** What the buttons send: a rating, and after a thumbs down optionally a reason and a comment. */
export type FeedbackInput = { rating: "up" | "down"; reason?: string; comment?: string };

export async function rateMatchResult(resultId: number, input: FeedbackInput): Promise<FeedbackResult> {
  const parsed = matchInput.safeParse(input);
  if (!id.safeParse(resultId).success || !parsed.success) return { ok: false, message: "Invalid feedback." };
  const body = { rating: parsed.data.rating, reason: parsed.data.reason ?? null, comment: parsed.data.comment || null };
  const result = await request((api) =>
    api.PUT("/api/match-results/{result_id}/feedback", { params: { path: { result_id: resultId } }, body }),
  );
  return result.ok ? { ok: true, feedback: result.data } : { ok: false, message: result.message };
}

export async function clearMatchFeedback(resultId: number): Promise<FeedbackResult> {
  if (!id.safeParse(resultId).success) return { ok: false, message: "Invalid." };
  const result = await request((api) =>
    api.DELETE("/api/match-results/{result_id}/feedback", { params: { path: { result_id: resultId } } }),
  );
  return result.ok ? { ok: true, feedback: null } : { ok: false, message: result.message };
}

export async function rateAgentAnswer(messageId: number, input: FeedbackInput): Promise<FeedbackResult> {
  const parsed = agentInput.safeParse(input);
  if (!id.safeParse(messageId).success || !parsed.success) return { ok: false, message: "Invalid feedback." };
  const body = { rating: parsed.data.rating, reason: parsed.data.reason ?? null, comment: parsed.data.comment || null };
  const result = await request((api) =>
    api.PUT("/api/agent/messages/{message_id}/feedback", { params: { path: { message_id: messageId } }, body }),
  );
  return result.ok ? { ok: true, feedback: result.data } : { ok: false, message: result.message };
}

export async function clearAgentFeedback(messageId: number): Promise<FeedbackResult> {
  if (!id.safeParse(messageId).success) return { ok: false, message: "Invalid." };
  const result = await request((api) =>
    api.DELETE("/api/agent/messages/{message_id}/feedback", { params: { path: { message_id: messageId } } }),
  );
  return result.ok ? { ok: true, feedback: null } : { ok: false, message: result.message };
}
