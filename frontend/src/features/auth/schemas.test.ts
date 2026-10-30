import { describe, expect, it } from "vitest";

import { loginSchema } from "./schemas";

describe("loginSchema", () => {
  it("trims and lower-cases the email", () => {
    const result = loginSchema.parse({ email: "  Admin@Company.LOCAL ", password: "x" });
    expect(result.email).toBe("admin@company.local");
  });

  it("accepts the company's .local addresses", () => {
    expect(loginSchema.safeParse({ email: "rm@company.local", password: "pw" }).success).toBe(true);
  });

  it("reports each problem on its own field", () => {
    const result = loginSchema.safeParse({ email: "not-an-email", password: "" });
    expect(result.success).toBe(false);
    const fields = result.error?.issues.map((issue) => issue.path[0]);
    expect(fields).toEqual(["email", "password"]);
  });

  it("treats a missing field (FormData.get -> null) as empty", () => {
    const result = loginSchema.safeParse({ email: null, password: null });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.message).toBe("Enter your email address.");
  });
});
