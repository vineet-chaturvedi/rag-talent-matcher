import { cn } from "@/lib/utils";

/** A 0-1 score as a labelled bar: "0.82" plus a bar 82% wide. role="meter" for screen readers. */
export function ScoreBar({
  label,
  value,
  className,
}: {
  label: string;
  value: number | null | undefined;
  className?: string;
}) {
  const v = value ?? 0;
  return (
    <div className={cn("grid grid-cols-[6.5rem_1fr_2.75rem] items-center gap-2 text-xs", className)}>
      <span className="text-muted-foreground">{label}</span>
      <span
        className="h-1.5 overflow-hidden rounded-full bg-muted"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={v}
      >
        <span className="block h-full rounded-full bg-primary" style={{ width: `${Math.round(v * 100)}%` }} />
      </span>
      <span className="text-right tabular-nums">{value == null ? "–" : v.toFixed(2)}</span>
    </div>
  );
}
