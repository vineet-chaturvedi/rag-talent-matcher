"use client";

import { Bot, FileText, FolderKanban, LayoutDashboard, type LucideIcon, ShieldCheck, Users } from "lucide-react";
import Link, { useLinkStatus } from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

import { isActive, type NavIcon, type NavItem } from "./navigation";

const ICONS: Record<NavIcon, LucideIcon> = {
  dashboard: LayoutDashboard,
  assistant: Bot,
  projects: FolderKanban,
  employees: Users,
  resumes: FileText,
  users: ShieldCheck,
};

/**
 * The menu links, with the current page marked. A Client Component only because it needs the current
 * URL (usePathname); everything else about the shell renders on the server.
 */
export function NavLinks({ items }: { items: readonly NavItem[] }) {
  const pathname = usePathname();
  return <NavList items={items} pathname={pathname} />;
}

/**
 * The same list WITHOUT reading the URL, for the loading fallback.
 * Why: a Suspense fallback is part of the prerendered shell, and on a dynamic route such as
 * /employees/[id] the URL isn't known when that shell is built. A fallback that calls usePathname()
 * fails the build ("URL data in a Client Component outside of Suspense"). Found when the first dynamic
 * route was added in Step 12.
 */
export function NavLinksStatic({ items }: { items: readonly NavItem[] }) {
  return <NavList items={items} pathname={null} />;
}

function NavList({ items, pathname }: { items: readonly NavItem[]; pathname: string | null }) {
  return (
    <ul className="flex gap-1 overflow-x-auto md:flex-col md:overflow-visible">
      {items.map((item) => {
        const active = pathname !== null && isActive(item, pathname);
        const Icon = ICONS[item.icon];
        return (
          <li key={item.href} className="shrink-0">
            <Link
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                active
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="size-4" aria-hidden />
              <span>{item.label}</span>
              <PendingDot />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Next.js 16's useLinkStatus: `pending` is true between the click and the new page appearing.
 * A small dot gives feedback on a slow network, without blocking anything.
 */
function PendingDot() {
  const { pending } = useLinkStatus();
  return (
    <span
      aria-hidden
      className={cn(
        "ml-auto size-1.5 rounded-full bg-primary transition-opacity",
        pending ? "animate-pulse opacity-100" : "opacity-0",
      )}
    />
  );
}
