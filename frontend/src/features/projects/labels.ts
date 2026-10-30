import type { MatchRunStatus, ProjectStatus, RoleStatus } from "@/lib/api/types";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

export const PROJECT_STATUS: readonly { value: ProjectStatus; label: string; tone: Tone }[] = [
  { value: "planned", label: "Planned", tone: "info" },
  { value: "active", label: "Active", tone: "success" },
  { value: "on_hold", label: "On hold", tone: "warning" },
  { value: "completed", label: "Completed", tone: "neutral" },
];

export const ROLE_STATUS: Record<RoleStatus, { label: string; tone: Tone }> = {
  open: { label: "Open", tone: "info" },
  filled: { label: "Filled", tone: "success" },
  closed: { label: "Closed", tone: "neutral" },
};

export const RUN_STATUS: Record<MatchRunStatus, { label: string; tone: Tone }> = {
  running: { label: "Judging…", tone: "info" },
  completed: { label: "Completed", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

/** The judge's overall rating (Step 8), as a colour. */
export const RATING_TONE: Record<"strong" | "good" | "partial" | "weak", Tone> = {
  strong: "success",
  good: "info",
  partial: "warning",
  weak: "danger",
};

/** One must-have: met / partly / not met. "Partly" is also what an unproven "yes" becomes. */
export const MET: Record<"yes" | "partly" | "no", { label: string; tone: Tone }> = {
  yes: { label: "Met", tone: "success" },
  partly: { label: "Partly", tone: "warning" },
  no: { label: "Not met", tone: "danger" },
};

export const SENIORITY = ["unspecified", "junior", "mid", "senior", "lead", "principal"] as const;

export const projectStatusLabel = (status: ProjectStatus) =>
  PROJECT_STATUS.find((s) => s.value === status)?.label ?? status;
export const projectStatusTone = (status: ProjectStatus) =>
  PROJECT_STATUS.find((s) => s.value === status)?.tone ?? "neutral";
