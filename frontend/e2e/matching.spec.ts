import { expect, test } from "@playwright/test";

import { logIn, requireCredentials } from "./helpers";

/**
 * Projects and matching (Step 12b). READ-ONLY: they open existing projects, roles and runs on your
 * real backend, but never create, parse, run or change anything (that costs LLM minutes and data).
 */
test.describe("projects and matching", () => {
  test.beforeEach(async ({ page }) => {
    requireCredentials();
    await logIn(page);
  });

  test("the projects page lists projects and offers to create one", async ({ page }) => {
    await page.goto("/projects");
    await expect(page.getByRole("heading", { name: "New project" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create project" })).toBeVisible();
  });

  test("an empty project name is explained by the server, not the browser", async ({ page }) => {
    await page.goto("/projects");
    // Submitting with an empty name: nothing is created; the form explains what is missing.
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page.getByText("Give the project a name")).toBeVisible();
    await expect(page).toHaveURL("/projects");
  });

  test("a role page shows its requirements and earlier runs", async ({ page }) => {
    await page.goto("/projects");
    // count() doesn't wait: first let the streamed project list replace its loading skeleton.
    await expect(page.getByRole("status", { name: "Loading projects" })).toHaveCount(0);
    const firstRole = page.locator('main a[href^="/roles/"]').first();
    test.skip((await firstRole.count()) === 0, "No roles exist yet.");
    await firstRole.click();
    await expect(page).toHaveURL(/\/roles\/\d+$/);
    await expect(page.getByRole("heading", { name: "Requirements" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Earlier runs" })).toBeVisible();
    // The menu still marks the section this page belongs to.
    await expect(page.getByRole("link", { name: "Projects & matching" })).toHaveAttribute("aria-current", "page");
  });

  test("a match run shows ranked candidates with their evidence", async ({ page }) => {
    await page.goto("/projects");
    // count() doesn't wait: first let the streamed project list replace its loading skeleton.
    await expect(page.getByRole("status", { name: "Loading projects" })).toHaveCount(0);
    const firstRole = page.locator('main a[href^="/roles/"]').first();
    test.skip((await firstRole.count()) === 0, "No roles exist yet.");
    await firstRole.click();
    await expect(page.getByRole("heading", { name: "Earlier runs" })).toBeVisible();
    await expect(
      page.locator('main a[href^="/match-runs/"]').first().or(page.getByText("No match runs yet")),
    ).toBeVisible();
    const firstRun = page.locator('main a[href^="/match-runs/"]').first();
    test.skip((await firstRun.count()) === 0, "This role has no match runs yet.");
    await firstRun.click();
    await expect(page.getByRole("heading", { name: /Best matches for/ })).toBeVisible();
    const candidates = page.getByRole("list", { name: "Ranked candidates" }).locator(":scope > li");
    await expect(candidates.first()).toBeVisible();
    await expect(candidates.first().getByText(/Must-haves: \d+ of \d+/)).toBeVisible();
  });

  test("unknown ids are 404s", async ({ page }) => {
    for (const path of ["/projects/99999999", "/roles/99999999", "/match-runs/abc"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
    }
  });
});
