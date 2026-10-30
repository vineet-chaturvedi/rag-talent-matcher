"use client";

import { ChevronsUpDown, LogOut, UserRound } from "lucide-react";
import Link from "next/link";
import { useRef } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { SessionUser } from "@/lib/auth/session";

import { logout } from "../actions";

const ROLE_LABEL: Record<SessionUser["role"], string> = {
  admin: "Administrator",
  resource_manager: "Resource manager",
};

/**
 * The signed-in person's menu (name, role, "Sign out").
 *
 * Sign out is a <form> posting to the `logout` Server Action, not an onClick handler: it works even
 * before JavaScript has loaded, and the server deletes the HttpOnly cookie (page JavaScript can't).
 * Importing a Server Action into a Client Component is allowed: what the browser gets is only a
 * reference (an ID) to call it on the server, never its code.
 *
 * Why the <form> sits OUTSIDE the menu and the item calls requestSubmit(): Radix renders the open
 * menu in a "portal" at the end of <body>, so a submit button there is not inside the form; and
 * selecting an item closes the menu, removing the item before the browser would submit. Two
 * browser-test findings (Step 11b, Step 12): the reliable way is to submit the form in code.
 */
export function AccountMenu({ user }: { user: SessionUser }) {
  const initials = user.fullName
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");

  const formRef = useRef<HTMLFormElement>(null);

  return (
    <DropdownMenu>
      <form ref={formRef} action={logout} hidden />
      <DropdownMenuTrigger className="flex w-full items-center gap-2.5 rounded-md p-1.5 text-left text-sm outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50 data-[state=open]:bg-muted">
        <span
          aria-hidden
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground"
        >
          {initials}
        </span>
        <span className="hidden min-w-0 flex-1 md:block">
          <span className="block truncate font-medium">{user.fullName}</span>
          <span className="block truncate text-xs text-muted-foreground">{ROLE_LABEL[user.role]}</span>
        </span>
        <span className="sr-only">Account menu for {user.fullName}</span>
        <ChevronsUpDown className="hidden size-4 text-muted-foreground md:block" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>
          <span className="block font-medium">{user.fullName}</span>
          <span className="block text-xs text-muted-foreground">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/account">
            <UserRound aria-hidden /> Account and password
          </Link>
        </DropdownMenuItem>
        {/* onSelect fires for a click AND for Enter/Space on the focused item. */}
        <DropdownMenuItem onSelect={() => formRef.current?.requestSubmit()}>
          <LogOut aria-hidden /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
