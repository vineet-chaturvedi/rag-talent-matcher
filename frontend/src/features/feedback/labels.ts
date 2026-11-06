import type { AgentFeedbackReason, MatchFeedbackReason } from "@/lib/api/types";

/**
 * The reasons offered after a thumbs down (Step 14c). Fixed lists, the same as FastAPI accepts, so
 * feedback can be counted ("12 × not available") and turned into test cases.
 */
export const MATCH_REASONS: readonly { value: MatchFeedbackReason; label: string }[] = [
  { value: "missing_skill", label: "Lacks a key skill" },
  { value: "too_little_experience", label: "Not enough experience" },
  { value: "not_available", label: "Not really available" },
  { value: "profile_wrong", label: "The profile is wrong (skills or years)" },
  { value: "should_rank_higher", label: "Should rank higher" },
  { value: "should_rank_lower", label: "Should rank lower" },
  { value: "other", label: "Something else" },
];

export const AGENT_REASONS: readonly { value: AgentFeedbackReason; label: string }[] = [
  { value: "wrong_people", label: "Named the wrong people" },
  { value: "missed_someone", label: "Missed someone who fits" },
  { value: "wrong_numbers", label: "Wrong years, dates or availability" },
  { value: "misunderstood", label: "Misunderstood the question" },
  { value: "too_long", label: "Too long or unclear" },
  { value: "other", label: "Something else" },
];

const ALL: Record<string, string> = Object.fromEntries(
  [...MATCH_REASONS, ...AGENT_REASONS].map((r) => [r.value, r.label]),
);

/** "not_available" -> "Not really available"; unknown values are shown as they are. */
export function reasonLabel(reason: string | null | undefined): string {
  return reason ? (ALL[reason] ?? reason) : "";
}
