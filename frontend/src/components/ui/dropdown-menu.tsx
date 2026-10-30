"use client";

import { DropdownMenu as DropdownMenuPrimitive } from "radix-ui";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * Dropdown menu (Radix). A menu looks simple but has many accessibility rules: arrow keys move
 * between items, Esc closes and returns focus to the button, typing a letter jumps to an item, the
 * screen reader hears "menu, 3 items". Radix implements the WAI-ARIA "menu button" pattern, so we
 * only add styles. Only the parts this app uses are exported; add more from shadcn/ui when needed.
 */
export const DropdownMenu = DropdownMenuPrimitive.Root;
export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;

export function DropdownMenuContent({
  className,
  sideOffset = 6,
  ...props
}: ComponentProps<typeof DropdownMenuPrimitive.Content>) {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Content
        data-slot="dropdown-menu-content"
        sideOffset={sideOffset}
        className={cn(
          "z-50 min-w-56 overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md",
          className,
        )}
        {...props}
      />
    </DropdownMenuPrimitive.Portal>
  );
}

export function DropdownMenuLabel({ className, ...props }: ComponentProps<typeof DropdownMenuPrimitive.Label>) {
  return <DropdownMenuPrimitive.Label className={cn("px-2 py-1.5 text-sm", className)} {...props} />;
}

export function DropdownMenuSeparator({ className, ...props }: ComponentProps<typeof DropdownMenuPrimitive.Separator>) {
  return <DropdownMenuPrimitive.Separator className={cn("-mx-1 my-1 h-px bg-border", className)} {...props} />;
}

export function DropdownMenuItem({ className, ...props }: ComponentProps<typeof DropdownMenuPrimitive.Item>) {
  return (
    <DropdownMenuPrimitive.Item
      className={cn(
        "relative flex cursor-default items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none select-none focus:bg-accent focus:text-accent-foreground data-disabled:pointer-events-none data-disabled:opacity-50 [&_svg]:size-4 [&_svg]:text-muted-foreground",
        className,
      )}
      {...props}
    />
  );
}
