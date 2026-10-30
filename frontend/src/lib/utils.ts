import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Join CSS class names, dropping empty ones and resolving Tailwind conflicts:
 *   cn("px-2 py-1", isActive && "bg-primary", "px-4")  ->  "py-1 bg-primary px-4"
 * (the later "px-4" wins over "px-2"). This is the helper every shadcn/ui component uses, so a
 * component's default classes can be overridden with a `className` prop.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** 1234 -> "1,234" (Indian English grouping is "1,234" too for numbers below a lakh). */
export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-IN").format(value);
}

/** "2026-12-01" -> "1 Dec 2026". Dates from the API are ISO strings; null stays empty. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(
    date,
  );
}

/** First word of a full name, for greetings ("Priya Sharma" -> "Priya"). */
export function firstName(fullName: string): string {
  return fullName.trim().split(/\s+/)[0] ?? "";
}
