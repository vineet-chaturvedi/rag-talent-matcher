import { describe, expect, it } from "vitest";

import { isActive, NAV_ITEMS, navItemsFor } from "./navigation";

const labels = (items: ReturnType<typeof navItemsFor>) => items.map((item) => item.label);

describe("navItemsFor", () => {
  it("shows admin-only pages to admins", () => {
    expect(labels(navItemsFor("admin"))).toContain("Users");
    expect(labels(navItemsFor("admin"))).toContain("Resumes");
    expect(labels(navItemsFor("admin"))).toContain("Feedback");
  });

  it("hides them from resource managers", () => {
    expect(labels(navItemsFor("resource_manager"))).not.toContain("Users");
    expect(labels(navItemsFor("resource_manager"))).not.toContain("Feedback");
    expect(labels(navItemsFor("resource_manager"))).toContain("Projects & matching");
  });

  it("shows only shared pages while the role is still loading", () => {
    expect(navItemsFor(null)).toEqual(navItemsFor("resource_manager"));
  });
});

describe("isActive", () => {
  const item = (label: string) => NAV_ITEMS.find((i) => i.label === label)!;
  it("marks a section on its own pages and its related pages", () => {
    expect(isActive(item("Projects & matching"), "/projects/3")).toBe(true);
    expect(isActive(item("Projects & matching"), "/roles/7")).toBe(true);
    expect(isActive(item("Projects & matching"), "/match-runs/12")).toBe(true);
    expect(isActive(item("Employees"), "/employees/5")).toBe(true);
  });
  it("does not match look-alike prefixes or the dashboard everywhere", () => {
    expect(isActive(item("Projects & matching"), "/projectsx")).toBe(false);
    expect(isActive(item("Dashboard"), "/employees")).toBe(false);
    expect(isActive(item("Dashboard"), "/")).toBe(true);
  });
});
