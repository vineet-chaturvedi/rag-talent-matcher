import type { Route } from "next";

import type { UserRole } from "@/lib/api/types";

/**
 * The portal's menu, in one place. `icon` is a NAME, not the icon component itself, because this list
 * is passed from Server Components to the (client) NavLinks component, and only plain data can cross
 * that boundary. NavLinks maps the name to the actual icon.
 */
export type NavIcon = "dashboard" | "assistant" | "projects" | "employees" | "resumes" | "users";

export type NavItem = {
  href: Route;
  label: string;
  icon: NavIcon;
  /** Only these roles see the item. Hiding is for convenience; FastAPI enforces the real rule. */
  roles?: readonly UserRole[];
};

export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/", label: "Dashboard", icon: "dashboard" },
  { href: "/agent", label: "Staffing assistant", icon: "assistant" },
  { href: "/projects", label: "Projects & matching", icon: "projects" },
  { href: "/employees", label: "Employees", icon: "employees" },
  { href: "/resumes", label: "Resumes", icon: "resumes", roles: ["admin"] },
  { href: "/users", label: "Users", icon: "users", roles: ["admin"] },
];

/** The items a role may see; with no role (still loading), only the items everyone sees. */
export function navItemsFor(role: UserRole | null): NavItem[] {
  return NAV_ITEMS.filter((item) => !item.roles || (role !== null && item.roles.includes(role)));
}
