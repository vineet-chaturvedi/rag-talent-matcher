import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Unit tests (Vitest + React Testing Library), as in the Next.js testing guide.
 * They cover pure logic (lib/) and synchronous components. Async Server Components and the full
 * login flow are covered by the Playwright end-to-end tests in e2e/ instead.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "src"),
      // "server-only" throws when imported outside a React Server environment; in unit tests we
      // import server modules on purpose, so replace it with an empty module.
      "server-only": path.resolve(import.meta.dirname, "vitest.empty.ts"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
});
