import type { ResumeStatus } from "@/lib/api/types";

/** Human names for the resume pipeline's states (Steps 3-6), in processing order. */
export const PIPELINE_STAGES: readonly { status: ResumeStatus; label: string }[] = [
  { status: "queued", label: "Queued" },
  { status: "parsing", label: "Reading file" },
  { status: "parsed", label: "Text ready" },
  { status: "extracting", label: "AI reading" },
  { status: "extracted", label: "Profile ready" },
  { status: "embedding", label: "Indexing" },
  { status: "ready", label: "Searchable" },
  { status: "failed", label: "Failed" },
];

/** States where the worker still has something to do: while any resume is in one, the dashboard auto-refreshes. */
export const IN_PROGRESS: readonly ResumeStatus[] = [
  "queued",
  "parsing",
  "parsed",
  "extracting",
  "extracted",
  "embedding",
];

/** The keys of /api/health's "models" object, as people say them. */
export const MODEL_LABEL: Record<string, string> = {
  embed_model: "Embedding model",
  fast_llm_model: "Fast LLM",
  quality_llm_model: "Quality LLM",
};
