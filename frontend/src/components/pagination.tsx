import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";

/**
 * Previous / Next links that keep the other URL parameters (search, filters).
 * The page number lives in the URL (?page=2), so a filtered page can be bookmarked, shared, reloaded,
 * and the browser's Back button works. That's why filters are links and GET forms, not React state.
 */
export function Pagination({
  pathname,
  params,
  page,
  hasNext,
}: {
  pathname: string;
  params: Record<string, string | undefined>;
  page: number;
  hasNext: boolean;
}) {
  if (page === 1 && !hasNext) return null;
  const href = (target: number) => {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) if (value) search.set(key, value);
    if (target > 1) search.set("page", String(target));
    const query = search.toString();
    return (query ? `${pathname}?${query}` : pathname) as Route;
  };
  return (
    <nav aria-label="Pages" className="flex items-center justify-between gap-2 pt-4">
      <span className="text-sm text-muted-foreground">Page {page}</span>
      <div className="flex gap-2">
        {page > 1 ? (
          <Button asChild variant="outline" size="sm">
            <Link href={href(page - 1)} rel="prev">
              <ChevronLeft aria-hidden /> Previous
            </Link>
          </Button>
        ) : (
          <Button variant="outline" size="sm" disabled>
            <ChevronLeft aria-hidden /> Previous
          </Button>
        )}
        {hasNext ? (
          <Button asChild variant="outline" size="sm">
            <Link href={href(page + 1)} rel="next">
              Next <ChevronRight aria-hidden />
            </Link>
          </Button>
        ) : (
          <Button variant="outline" size="sm" disabled>
            Next <ChevronRight aria-hidden />
          </Button>
        )}
      </div>
    </nav>
  );
}
