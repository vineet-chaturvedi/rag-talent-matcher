/**
 * npm run api:types
 *
 * Regenerates src/lib/api/schema.d.ts from the running FastAPI's OpenAPI document, so the frontend's
 * TypeScript types always match the backend's Pydantic models. Run it after changing an API in the
 * backend (the backend must be running). Then `npm run typecheck` shows every place that must change.
 *
 * Reads BACKEND_URL from the environment or .env.local (default http://127.0.0.1:8010).
 */
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import openapiTS, { astToString } from "openapi-typescript";

function backendUrl() {
  if (process.env.BACKEND_URL) return process.env.BACKEND_URL;
  if (existsSync(".env.local")) {
    const line = readFileSync(".env.local", "utf8")
      .split(/\r?\n/)
      .find((l) => l.trim().startsWith("BACKEND_URL="));
    if (line)
      return line
        .split("=")
        .slice(1)
        .join("=")
        .trim()
        .replace(/^["']|["']$/g, "");
  }
  return "http://127.0.0.1:8010";
}

const url = `${backendUrl().replace(/\/+$/, "")}/openapi.json`;
const target = "src/lib/api/schema.d.ts";

try {
  const ast = await openapiTS(new URL(url));
  const header =
    "/**\n * GENERATED FILE: do not edit by hand.\n" +
    ` * Source: ${url}\n * Regenerate with: npm run api:types\n */\n\n`;
  writeFileSync(target, header + astToString(ast));
  console.log(`Wrote ${target} from ${url}`);
} catch (error) {
  console.error(`Could not read ${url}. Is the backend running?\n${error instanceof Error ? error.message : error}`);
  process.exit(1);
}
