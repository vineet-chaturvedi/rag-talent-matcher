import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * Card: a white panel with a border. Built from small parts (shadcn/ui "composition" style) so each
 * page arranges them as it needs:
 *   <Card>
 *     <CardHeader><CardTitle>System health</CardTitle><CardAction>...</CardAction></CardHeader>
 *     <CardContent>...</CardContent>
 *   </Card>
 */
export function Card({ className, ...props }: ComponentProps<"section">) {
  return (
    <section
      data-slot="card"
      className={cn("flex flex-col gap-4 rounded-xl border bg-card py-5 text-card-foreground shadow-xs", className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn("flex flex-wrap items-start justify-between gap-x-4 gap-y-1 px-5", className)}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: ComponentProps<"h2">) {
  return <h2 data-slot="card-title" className={cn("text-sm leading-6 font-semibold", className)} {...props} />;
}

export function CardDescription({ className, ...props }: ComponentProps<"p">) {
  return <p data-slot="card-description" className={cn("text-sm text-muted-foreground", className)} {...props} />;
}

export function CardAction({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="card-action" className={cn("ml-auto flex items-center gap-2", className)} {...props} />;
}

export function CardContent({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="card-content" className={cn("px-5", className)} {...props} />;
}
