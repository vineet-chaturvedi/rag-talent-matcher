import "server-only";

import { parseEnv } from "./schema";

/**
 * The validated settings, for server code only (Data Access Layer, Server Actions, Route Handlers).
 *
 * `import "server-only"` makes the BUILD fail if a Client Component ever imports this file, so a
 * secret added here later can never be bundled into the JavaScript that goes to the browser.
 */
export const env = parseEnv(process.env);
