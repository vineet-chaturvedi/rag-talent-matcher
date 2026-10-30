import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests: a real browser against the real Next.js server and the real FastAPI backend.
 *
 * Before running:
 *   1. the backend is running (uvicorn on port 8010) and a portal user exists;
 *   2. set E2E_EMAIL and E2E_PASSWORD to that user's login (PowerShell: $env:E2E_EMAIL="...").
 * Then: npm run test:e2e   (it builds and starts Next.js on port 3100 by itself).
 * First time only: npx playwright install chromium
 */
const PORT = Number(process.env.E2E_PORT ?? 3100);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // the tests share one backend and one user: keep them in order
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure", // a step-by-step recording when a test fails (npx playwright show-trace)
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    // A production build with the instant-navigation testing API switched on (see next.config.ts).
    command: `npx next build && npx next start --port ${PORT}`,
    url: `http://localhost:${PORT}/login`,
    reuseExistingServer: !process.env.CI,
    timeout: 240_000,
    env: { EXPOSE_TESTING_API: "1" },
  },
});
