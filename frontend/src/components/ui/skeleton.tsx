import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * A grey placeholder shaped like the content that is loading. Better than a spinner: the layout
 * doesn't jump when the data arrives, and the page feels faster because its structure is visible
 * immediately. Hidden from screen readers; the surrounding Suspense fallback says "Loading ...".
 */
export function Skeleton({ className, ...props }: ComponentProps<"div">) {
  return (
    <div data-slot="skeleton" aria-hidden className={cn("animate-pulse rounded-md bg-muted", className)} {...props} />
  );
}
