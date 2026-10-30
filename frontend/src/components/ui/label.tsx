"use client";

import { Label as LabelPrimitive } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * Form label (Radix). Clicking it focuses its input (htmlFor), and it stops double-click text
 * selection on the label, the small details Radix gets right so we don't have to.
 */
export function Label({ className, ...props }: ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      data-slot="label"
      className={cn("text-sm leading-none font-medium select-none", className)}
      {...props}
    />
  );
}
