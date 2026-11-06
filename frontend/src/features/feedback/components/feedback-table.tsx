import { MessageSquareText, ThumbsDown, ThumbsUp } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Pagination } from "@/components/pagination";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { FeedbackItem, FeedbackRating, FeedbackTarget } from "@/lib/api/types";
import { cn, formatDateTime } from "@/lib/utils";

import { reasonLabel } from "../labels";
import { FEEDBACK_PAGE_SIZE, listFeedback } from "../queries";

type Filters = { target?: FeedbackTarget; rating?: FeedbackRating };

/**
 * What colleagues said about matches and answers (admins). Each row is one labelled example; the
 * context columns show what the person was looking at when they rated it, even if the run or the
 * conversation was deleted later. `scripts/export_feedback.py` turns these into test data (doc 19).
 */
export async function FeedbackTable({ target, rating, page }: Filters & { page: number }) {
  const result = await listFeedback(target, rating, page);
  if (!result.ok) return <Alert>{result.message}</Alert>;
  const { counts } = result.data;
  const items = result.data.items.slice(0, FEEDBACK_PAGE_SIZE);
  const hasNext = result.data.items.length > FEEDBACK_PAGE_SIZE;

  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Matches 👍" value={counts.match_up} />
        <Tile label="Matches 👎" value={counts.match_down} />
        <Tile label="Answers 👍" value={counts.agent_up} />
        <Tile label="Answers 👎" value={counts.agent_down} />
      </dl>
      <FilterLinks {...{ target, rating }} />
      {items.length === 0 ? (
        <EmptyState icon={MessageSquareText} title="No feedback yet">
          Ratings appear here when people press 👍 or 👎 on a match result or an assistant answer.
        </EmptyState>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Rating</TableHead>
              <TableHead>About</TableHead>
              <TableHead>Why</TableHead>
              <TableHead>By</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="align-top">
                  {item.rating === "up" ? (
                    <ThumbsUp className="size-4 text-success" aria-label="Thumbs up" />
                  ) : (
                    <ThumbsDown className="size-4 text-destructive" aria-label="Thumbs down" />
                  )}
                </TableCell>
                <TableCell className="max-w-md align-top">
                  <About item={item} />
                </TableCell>
                <TableCell className="max-w-64 align-top text-sm">
                  {item.reason && <span className="block font-medium">{reasonLabel(item.reason)}</span>}
                  {item.comment && (
                    <span className="block whitespace-pre-line text-muted-foreground">{item.comment}</span>
                  )}
                  {!item.reason && !item.comment && <span className="text-muted-foreground">–</span>}
                </TableCell>
                <TableCell className="align-top text-xs whitespace-nowrap text-muted-foreground">
                  {item.user_name}
                  <span className="block">{formatDateTime(item.updated_at)}</span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Pagination pathname="/feedback" params={{ target, rating }} page={page} hasNext={hasNext} />
    </div>
  );
}

function About({ item }: { item: FeedbackItem }) {
  const ctx = (item.context ?? {}) as Record<string, unknown>;
  if (item.target === "match_result") {
    return (
      <div className="space-y-0.5 text-sm">
        <p>
          {item.employee_id ? (
            <Link href={`/employees/${item.employee_id}` as Route} className="font-medium hover:underline">
              {item.employee_name}
            </Link>
          ) : (
            <span className="font-medium">A removed employee</span>
          )}{" "}
          <span className="text-muted-foreground">{item.employee_code}</span>
        </p>
        <p className="text-xs text-muted-foreground">
          for {item.role_title ?? String(ctx.role_title ?? "a role")}
          {typeof ctx.rank === "number" && ` · ranked #${ctx.rank}`}
          {typeof ctx.final_score === "number" && ` · score ${ctx.final_score.toFixed(2)}`}
          {item.match_run_id && (
            <>
              {" · "}
              <Link href={`/match-runs/${item.match_run_id}` as Route} className="text-primary hover:underline">
                run #{item.match_run_id}
              </Link>
            </>
          )}
        </p>
      </div>
    );
  }
  const calls = Array.isArray(ctx.tool_calls) ? (ctx.tool_calls as { name?: string }[]) : [];
  return (
    <div className="space-y-1 text-sm">
      <p className="font-medium">“{String(ctx.question ?? "(question not kept)")}”</p>
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer select-none">
          The answer{calls.length > 0 && ` · used ${calls.map((c) => c.name).join(", ")}`}
        </summary>
        <p className="mt-1 whitespace-pre-line">{String(ctx.answer ?? "")}</p>
      </details>
    </div>
  );
}

function Tile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border bg-card px-4 py-3">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-xl font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

function FilterLinks({ target, rating }: Filters) {
  const href = (t?: FeedbackTarget, r?: FeedbackRating) => {
    const q = new URLSearchParams();
    if (t) q.set("target", t);
    if (r) q.set("rating", r);
    const s = q.toString();
    return (s ? `/feedback?${s}` : "/feedback") as Route;
  };
  const group = (label: string, options: { label: string; href: Route; current: boolean }[]) => (
    <nav aria-label={label} className="flex flex-wrap gap-1.5">
      {options.map((o) => (
        <Link
          key={o.label}
          href={o.href}
          aria-current={o.current ? "page" : undefined}
          className={cn(
            "rounded-full border px-3 py-1 text-xs font-medium transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
            o.current ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-muted",
          )}
        >
          {o.label}
        </Link>
      ))}
    </nav>
  );
  return (
    <div className="flex flex-wrap gap-4">
      {group("Filter by what was rated", [
        { label: "Everything", href: href(undefined, rating), current: !target },
        { label: "Match results", href: href("match_result", rating), current: target === "match_result" },
        { label: "Assistant answers", href: href("agent_answer", rating), current: target === "agent_answer" },
      ])}
      {group("Filter by rating", [
        { label: "Both", href: href(target, undefined), current: !rating },
        { label: "👍 only", href: href(target, "up"), current: rating === "up" },
        { label: "👎 only", href: href(target, "down"), current: rating === "down" },
      ])}
    </div>
  );
}

export function FeedbackTableSkeleton() {
  return (
    <div className="space-y-3" role="status" aria-label="Loading the feedback">
      <Skeleton className="h-16 w-full" />
      {Array.from({ length: 4 }, (_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}
