import { describe, expect, it } from "vitest";

import { safeNextPath } from "./redirect";

describe("safeNextPath", () => {
  it.each([
    ["/projects", "/projects"],
    ["/projects?role=3#matches", "/projects?role=3#matches"],
    ["/", "/"],
  ])("keeps the same-site path %s", (input, expected) => {
    expect(safeNextPath(input)).toBe(expected);
  });

  it.each([
    ["https://evil.example/login"], // absolute URL to another site
    ["//evil.example"], // protocol-relative: the browser treats it as another site
    ["/\\evil.example"], // backslash trick
    ["javascript:alert(1)"],
    ["projects"], // not a path
    ["/login"], // would loop back to the login page
    ["/login?next=/x"],
    ["/auth/session-expired"],
    ["/projects\nSet-Cookie: x=1"], // control characters
    [""],
    [null],
    [42],
  ])("falls back to the dashboard for %j", (input) => {
    expect(safeNextPath(input)).toBe("/");
  });
});
