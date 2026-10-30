import { expect, type Page, test } from "@playwright/test";

/** The portal user the tests log in as (any existing user works; admin sees every page). */
export const credentials = {
  email: process.env.E2E_EMAIL ?? "",
  password: process.env.E2E_PASSWORD ?? "",
};

/** Skip (rather than fail) when no test user is configured, with a message saying what to set. */
export function requireCredentials() {
  test.skip(!credentials.email || !credentials.password, "Set E2E_EMAIL and E2E_PASSWORD to a portal user's login.");
}

/** Log in through the real form, exactly as a person would. */
export async function logIn(page: Page, next?: string) {
  await page.goto(next ? `/login?next=${encodeURIComponent(next)}` : "/login");
  await page.getByLabel("Email").fill(credentials.email);
  await page.getByLabel("Password").fill(credentials.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}
