import { describe, expect, it } from "vitest";

import { navItemsFor } from "./navigation";

const labels = (items: ReturnType<typeof navItemsFor>) => items.map((item) => item.label);

describe("navItemsFor", () => {
  it("shows admin-only pages to admins", () => {
    expect(labels(navItemsFor("admin"))).toContain("Users");
    expect(labels(navItemsFor("admin"))).toContain("Resumes");
  });

  it("hides them from resource managers", () => {
    expect(labels(navItemsFor("resource_manager"))).not.toContain("Users");
    expect(labels(navItemsFor("resource_manager"))).toContain("Projects & matching");
  });

  it("shows only shared pages while the role is still loading", () => {
    expect(navItemsFor(null)).toEqual(navItemsFor("resource_manager"));
  });
});
