import { expect, test } from "@playwright/test";

import { logIn, requireCredentials } from "./helpers";

/**
 * Employees and resumes (Step 12a). READ-ONLY on purpose: these tests run against your real backend,
 * so they never upload, retry or delete anything.
 */
test.describe("employees and resumes", () => {
  test.beforeEach(async ({ page }) => {
    requireCredentials();
    await logIn(page);
  });

  test("search narrows the employee list and is kept in the URL", async ({ page }) => {
    await page.goto("/employees");
    const rows = page.locator("tbody tr");
    await expect(rows.first()).toBeVisible();
    const firstName = (await rows.first().getByRole("link").innerText()).split(" ")[0]!;

    await page.getByRole("searchbox", { name: "Search" }).fill(firstName);
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page).toHaveURL(new RegExp(`q=${firstName}`));
    await expect(rows.first()).toContainText(firstName);
  });

  test("broken URL parameters show a normal page instead of an error", async ({ page }) => {
    await page.goto("/employees?page=-3&availability=%3Cscript%3E");
    await expect(page.getByRole("heading", { name: "Employees", level: 1 })).toBeVisible();
    await expect(page.locator("tbody tr").first()).toBeVisible();
  });

  test("an employee page shows the AI profile with evidence", async ({ page }) => {
    await page.goto("/employees");
    await page.locator("tbody tr").first().getByRole("link").click();
    await expect(page).toHaveURL(/\/employees\/\d+$/);
    await expect(page.getByRole("heading", { name: "Resume versions" })).toBeVisible();
    // Either the profile (skills with evidence) or a clear "no profile yet" message.
    await expect(
      page.getByRole("heading", { name: "Skills" }).or(page.getByText(/No (AI profile|resume) yet/)),
    ).toBeVisible();
  });

  test("an unknown employee id is a 404", async ({ page }) => {
    await page.goto("/employees/99999999");
    await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  });

  test("admins see the resume pipeline with status filters", async ({ page }) => {
    await page.goto("/resumes");
    const filters = page.getByRole("navigation", { name: "Filter by status" });
    // Resource managers see "Administrators only" instead; this test user is expected to be an admin.
    await expect(filters).toBeVisible();
    await filters.getByRole("link", { name: /Failed/ }).click();
    await expect(page).toHaveURL("/resumes?status=failed");
    await expect(filters.getByRole("link", { name: /Failed/ })).toHaveAttribute("aria-current", "page");
  });
});
