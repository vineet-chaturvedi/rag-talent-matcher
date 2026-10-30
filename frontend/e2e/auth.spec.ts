import { expect, test } from "@playwright/test";

import { credentials, logIn, requireCredentials } from "./helpers";

test.describe("signing in and out", () => {
  test("a visitor without a session is sent to the login page, remembering where they wanted to go", async ({
    page,
  }) => {
    await page.goto("/projects");
    await expect(page).toHaveURL("/login?next=%2Fprojects");
    await expect(page.getByRole("heading", { name: "Talent Matcher" })).toBeVisible();
  });

  test("the browser validates nothing the server doesn't: an invalid email is reported by the server", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("not-an-email");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("That doesn't look like an email address.")).toBeVisible();
    await expect(page.getByLabel("Email")).toHaveAttribute("aria-invalid", "true");
  });

  test("a wrong password shows the backend's message and keeps the email", async ({ page }) => {
    requireCredentials();
    await page.goto("/login");
    await page.getByLabel("Email").fill(credentials.email);
    await page.getByLabel("Password").fill("definitely-not-the-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    // filter: Next.js also has an (empty) role="alert" element that announces page changes.
    await expect(page.getByRole("alert").filter({ hasText: "Wrong email or password." })).toBeVisible();
    await expect(page.getByLabel("Email")).toHaveValue(credentials.email);
  });

  test("logging in returns to the page that was asked for; signing out ends the session", async ({ page }) => {
    requireCredentials();
    await logIn(page, "/projects");
    await expect(page).toHaveURL("/projects");
    await expect(page.getByRole("heading", { name: "Projects & matching" })).toBeVisible();

    // The cookie is HttpOnly: it exists, but page JavaScript can't read it.
    const cookie = (await page.context().cookies()).find((c) => c.name === "rtm_access");
    expect(cookie?.httpOnly).toBe(true);
    expect(await page.evaluate(() => document.cookie)).not.toContain("rtm_access");

    await page
      .getByRole("button", { name: /Account menu/ })
      .filter({ visible: true })
      .click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await expect(page).toHaveURL("/login");
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });

  test("an invalid session (forged or revoked token) is cleared and explained", async ({ page, context }) => {
    // Looks valid to the proxy (expires in an hour) but FastAPI rejects the signature.
    const b64 = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");
    const forged = `${b64({ alg: "HS256" })}.${b64({ sub: "1", exp: Math.floor(Date.now() / 1000) + 3600 })}.bad`;
    await context.addCookies([{ name: "rtm_access", value: forged, url: "http://localhost:3100" }]);

    await page.goto("/");
    await expect(page).toHaveURL("/login?expired=1");
    await expect(page.getByRole("status").filter({ hasText: "Your session has ended" })).toBeVisible();
    expect((await context.cookies()).find((c) => c.name === "rtm_access")).toBeUndefined();
  });
});

test.describe("without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("the login form still works (progressive enhancement with a Server Action)", async ({ page }) => {
    requireCredentials();
    await page.goto("/login");
    await page.getByLabel("Email").fill(credentials.email);
    await page.getByLabel("Password").fill(credentials.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL("/");
  });
});
