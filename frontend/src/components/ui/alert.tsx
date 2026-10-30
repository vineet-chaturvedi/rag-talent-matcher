import { cva, type VariantProps } from "class-variance-authority";
import { CircleAlert, Info, TriangleAlert } from "lucide-react";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * A message box. `role="alert"` makes screen readers announce errors as soon as they appear;
 * informational notes use `role="status"`, which is announced politely (after the current sentence).
 */
const alertVariants = cva("flex items-start gap-3 rounded-lg border px-4 py-3 text-sm [&>svg]:mt-0.5 [&>svg]:size-4", {
  variants: {
    tone: {
      info: "border-primary/20 bg-primary/5 text-foreground [&>svg]:text-primary",
      warning: "border-warning/30 bg-warning/10 text-foreground [&>svg]:text-warning",
      danger: "border-destructive/30 bg-destructive/5 text-foreground [&>svg]:text-destructive",
    },
  },
  defaultVariants: { tone: "danger" },
});

const ICONS = { info: Info, warning: TriangleAlert, danger: CircleAlert } as const;

export function Alert({
  className,
  tone = "danger",
  title,
  children,
  ...props
}: ComponentProps<"div"> & VariantProps<typeof alertVariants> & { title?: string }) {
  const Icon = ICONS[tone ?? "danger"];
  return (
    <div
      data-slot="alert"
      role={tone === "danger" ? "alert" : "status"}
      className={cn(alertVariants({ tone }), className)}
      {...props}
    >
      <Icon aria-hidden />
      <div className="space-y-1">
        {title && <p className="font-medium">{title}</p>}
        <div className="text-muted-foreground">{children}</div>
      </div>
    </div>
  );
}
