import type { AvailabilityStatus } from "@/lib/api/types";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

export const AVAILABILITY: readonly { value: AvailabilityStatus; label: string; tone: Tone }[] = [
  { value: "available", label: "Available", tone: "success" },
  { value: "partial", label: "Partly allocated", tone: "info" },
  { value: "allocated", label: "Fully allocated", tone: "neutral" },
  { value: "on_leave", label: "On leave", tone: "warning" },
];

export const AVAILABILITY_VALUES = AVAILABILITY.map((a) => a.value);
export const AVAILABILITY_LABEL = Object.fromEntries(AVAILABILITY.map((a) => [a.value, a.label])) as Record<
  AvailabilityStatus,
  string
>;
export const AVAILABILITY_TONE = Object.fromEntries(AVAILABILITY.map((a) => [a.value, a.tone])) as Record<
  AvailabilityStatus,
  Tone
>;
