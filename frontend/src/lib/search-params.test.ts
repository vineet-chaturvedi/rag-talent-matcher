import { describe, expect, it } from "vitest";

import { enumParam, idParam, pageParam, textParam } from "./search-params";

describe("URL parameters", () => {
  it("pageParam accepts positive integers and falls back to 1", () => {
    expect(pageParam("3")).toBe(3);
    expect(pageParam(["2", "9"])).toBe(2); // repeated parameter: the first wins
    for (const bad of [undefined, "", "0", "-4", "abc", "1.5", "99999999"]) expect(pageParam(bad)).toBe(1);
  });

  it("enumParam only lets known values through", () => {
    const allowed = ["ready", "failed"] as const;
    expect(enumParam("failed", allowed)).toBe("failed");
    expect(enumParam("<script>", allowed)).toBeUndefined();
    expect(enumParam(undefined, allowed)).toBeUndefined();
  });

  it("textParam trims, limits length and drops empty values", () => {
    expect(textParam("  python ")).toBe("python");
    expect(textParam("   ")).toBeUndefined();
    expect(textParam("x".repeat(500))?.length).toBe(100);
  });

  it("idParam accepts only positive integer ids", () => {
    expect(idParam("7")).toBe(7);
    for (const bad of ["0", "-1", "abc", "7.5", undefined]) expect(idParam(bad)).toBeNull();
  });
});
