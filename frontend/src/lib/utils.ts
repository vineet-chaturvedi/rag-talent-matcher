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

/**
 * "2026-10-27T09:06:32" -> "27 Oct 2026, 2:36 pm". FastAPI sends UTC times without a "Z", so we add
 * it before parsing; the time is then shown in the server's time zone (your PC: India Standard Time).
 */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "";
  const iso = /[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

/** 37370 -> "36.5 KB". */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}

/** (1, "resume") -> "1 resume"; (3, "resume") -> "3 resumes". */
export function plural(count: number, word: string, pluralWord = `${word}s`): string {
  return `${formatNumber(count)} ${count === 1 ? word : pluralWord}`;
}
