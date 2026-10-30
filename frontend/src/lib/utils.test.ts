import { describe, expect, it } from "vitest";

import { formatBytes, formatDateTime, plural } from "./utils";

describe("formatting helpers", () => {
  it("formatBytes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(37370)).toBe("36 KB");
    expect(formatBytes(2318)).toBe("2.3 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });

  it("plural", () => {
    expect(plural(1, "page")).toBe("1 page");
    expect(plural(3, "page")).toBe("3 pages");
    expect(plural(0, "resume")).toBe("0 resumes");
  });

  it("formatDateTime treats FastAPI's time as UTC and tolerates bad input", () => {
    const naive = formatDateTime("2026-10-27T09:06:32");
    expect(naive).toBe(formatDateTime("2026-10-27T09:06:32Z"));
    expect(formatDateTime(null)).toBe("");
    expect(formatDateTime("not a date")).toBe("not a date");
  });
});
