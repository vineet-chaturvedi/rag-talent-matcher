import type { NextConfig } from "next";

import { parseEnv } from "./src/lib/env/schema";

/**
 * Next.js configuration.
 *
 * 1. Rendering: Cache Components + Partial Prefetching (the Next.js 16 model). Pages are a static
 *    shell that appears instantly; anything that needs the request (the login cookie, live data)
 *    streams in behind <Suspense> boundaries.
 * 2. Compiler: the React Compiler memoises components automatically (no hand-written useMemo).
 * 3. Typed routes: <Link href="/emplyees"> (a typo) becomes a TypeScript error.
 * 4. Rewrites: browser code that must call FastAPI directly (the agent's live stream, file uploads
 *    with progress, Steps 12-13) calls /api/... on this server, which forwards it to BACKEND_URL.
 *    Pages and Server Actions do NOT use this: they call FastAPI server-to-server (src/lib/api).
 * 5. Security headers on every response.
 */
const env = parseEnv(process.env);
const isDev = env.NODE_ENV === "development";

/**
 * Content-Security-Policy: the browser refuses any script, style, image or connection that doesn't
 * come from this site. It is the main defence against cross-site scripting (XSS): even if an attacker
 * manages to inject HTML, the browser won't run their script or send data to their server.
 *
 * Why 'unsafe-inline' for scripts: Next.js puts small inline <script> tags in the HTML (the data the
 * page needs to hydrate). The strict alternative is a per-request nonce, but a nonce forces EVERY page
 * to render on each request and is incompatible with the prerendered static shell that Cache
 * Components builds. The Next.js docs offer this "without nonces" policy for that case.
 * 'unsafe-eval' is only needed in development (React uses eval for better error stacks).
 */
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' blob: data:",
  "font-src 'self'",
  "connect-src 'self'", // fetch/SSE only to this site (FastAPI is reached through it)
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'", // nobody may put the portal in an <iframe> (clickjacking)
  ...(env.HTTPS ? ["upgrade-insecure-requests"] : []),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" }, // don't guess file types (stops "image" that is really a script)
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" }, // don't leak internal URLs to other sites
  { key: "X-Frame-Options", value: "DENY" }, // older browsers' version of frame-ancestors
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  ...(env.HTTPS ? [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }] : []),
];

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  reactCompiler: true,
  typedRoutes: true,
  poweredByHeader: false, // don't advertise the framework in every response
  turbopack: {
    rules: {
      "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" },
    },
  },
  experimental: {
    // Lets the e2e tests freeze the page at its instant (prefetched) state. Test builds only.
    exposeTestingApiInProductionBuild: process.env.EXPOSE_TESTING_API === "1",
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${env.BACKEND_URL}/api/:path*` }];
  },
};

export default nextConfig;
