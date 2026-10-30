import { describe, expect, it } from "vitest";

import { parseEnv } from "./schema";

describe("parseEnv", () => {
  it("applies defaults when nothing is set", () => {
    expect(parseEnv({})).toEqual({ BACKEND_URL: "http://127.0.0.1:8010", HTTPS: false, NODE_ENV: "development" });
  });

  it("removes a trailing slash and reads boolean flags", () => {
    const env = parseEnv({ BACKEND_URL: "http://api.internal:9000/", HTTPS: "TRUE", NODE_ENV: "production" });
    expect(env).toEqual({ BACKEND_URL: "http://api.internal:9000", HTTPS: true, NODE_ENV: "production" });
  });

  it("names the bad variable in the error", () => {
    expect(() => parseEnv({ BACKEND_URL: "localhost:8010" })).toThrow(/BACKEND_URL must be a full URL/);
    expect(() => parseEnv({ BACKEND_URL: "ftp://files.internal" })).toThrow(/BACKEND_URL/);
    expect(() => parseEnv({ NODE_ENV: "staging" })).toThrow(/NODE_ENV/);
  });
});
