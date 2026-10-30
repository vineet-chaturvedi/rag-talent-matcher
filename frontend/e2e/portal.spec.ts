import { instant } from "@next/playwright";
import { expect, test } from "@playwright/test";

import { logIn, requireCredentials } from "./helpers";

test.describe("the portal", () => {
  test.beforeEach(async ({ page }) => {
    requireCredentials();
    await logIn(page);
  });

  test("the dashboard streams in every section", async ({ page }) => {
    await expect(page.getByRole("heading", { level: 1 })).toContainText(/Good to see you|Dashboard/);
    await expect(page.getByText("Employees", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "System health" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Resume pipeline" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Projects and open roles" })).toBeVisible();
    await expect(page.getByRole("status", { name: /Loading/ })).toHaveCount(0); // every skeleton replaced
  });

  test("navigating to another page is instant: its heading shows before any data arrives", async ({ page }) => {
    // instant() freezes request-time data, so only the prefetched shell may render inside it.
    await instant(page, async () => {
      await page.getByRole("link", { name: "Employees" }).click();
      await expect(page.getByRole("heading", { name: "Employees", level: 1 })).toBeVisible();
    });
    await expect(page).toHaveURL("/employees");
  });

  test("the current page is marked in the menu", async ({ page }) => {
    await page.getByRole("link", { name: "Projects & matching" }).click();
    await expect(page.getByRole("link", { name: "Projects & matching" })).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("link", { name: "Dashboard" })).not.toHaveAttribute("aria-current");
  });

  test("security headers are sent with every page", async ({ page }) => {
    const response = await page.goto("/");
    const headers = response!.headers();
    expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["x-powered-by"]).toBeUndefined();
  });
});
