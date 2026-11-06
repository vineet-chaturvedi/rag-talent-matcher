import type { Route } from "next";

import type { UserRole } from "@/lib/api/types";

/**
 * The portal's menu, in one place. `icon` is a NAME, not the icon component itself, because this list
 * is passed from Server Components to the (client) NavLinks component, and only plain data can cross
 * that boundary. NavLinks maps the name to the actual icon.
 */
export type NavIcon = "dashboard" | "assistant" | "projects" | "employees" | "resumes" | "feedback" | "users";

export type NavItem = {
  href: Route;
  label: string;
  icon: NavIcon;
  /** Only these roles see the item. Hiding is for convenience; FastAPI enforces the real rule. */
  roles?: readonly UserRole[];
  /** Other URL prefixes that belong to this item (a role page belongs to "Projects & matching"). */
  also?: readonly string[];
};

export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/", label: "Dashboard", icon: "dashboard" },
  { href: "/agent", label: "Staffing assistant", icon: "assistant" },
  { href: "/projects", label: "Projects & matching", icon: "projects", also: ["/roles", "/match-runs"] },
  { href: "/employees", label: "Employees", icon: "employees" },
  { href: "/resumes", label: "Resumes", icon: "resumes", roles: ["admin"] },
  { href: "/feedback", label: "Feedback", icon: "feedback", roles: ["admin"] },
  { href: "/users", label: "Users", icon: "users", roles: ["admin"] },
];

/** The items a role may see; with no role (still loading), only the items everyone sees. */
export function navItemsFor(role: UserRole | null): NavItem[] {
  return NAV_ITEMS.filter((item) => !item.roles || (role !== null && item.roles.includes(role)));
}

/** Is this menu item the current section? "/" only matches itself; others match their sub-pages. */
export function isActive(item: NavItem, pathname: string): boolean {
  if (item.href === "/") return pathname === "/";
  return [item.href, ...(item.also ?? [])].some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}
