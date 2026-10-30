import type { ResumeStatus } from "@/lib/api/types";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

/** The resume pipeline (Steps 3-6), in processing order, as people say it. Shared by every page. */
export const PIPELINE_STAGES: readonly { status: ResumeStatus; label: string; tone: Tone }[] = [
  { status: "queued", label: "Queued", tone: "neutral" },
  { status: "parsing", label: "Reading file", tone: "info" },
  { status: "parsed", label: "Text ready", tone: "info" },
  { status: "extracting", label: "AI reading", tone: "info" },
  { status: "extracted", label: "Profile ready", tone: "info" },
  { status: "embedding", label: "Indexing", tone: "info" },
  { status: "ready", label: "Searchable", tone: "success" },
  { status: "failed", label: "Failed", tone: "danger" },
];

export const STATUS_LABEL = Object.fromEntries(PIPELINE_STAGES.map((s) => [s.status, s.label])) as Record<
  ResumeStatus,
  string
>;
export const STATUS_TONE = Object.fromEntries(PIPELINE_STAGES.map((s) => [s.status, s.tone])) as Record<
  ResumeStatus,
  Tone
>;

/** States where the worker still has something to do: pages showing them refresh themselves. */
export const IN_PROGRESS: readonly ResumeStatus[] = [
  "queued",
  "parsing",
  "parsed",
  "extracting",
  "extracted",
  "embedding",
];

export const isInProgress = (status: ResumeStatus) => IN_PROGRESS.includes(status);
