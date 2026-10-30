import { describe, expect, it } from "vitest";

import { formValues, matchSchema, projectSchema, requirementsSchema, roleSchema } from "./schemas";

describe("projectSchema", () => {
  it("turns empty optional fields into null", () => {
    const parsed = projectSchema.parse({ name: " Claims Portal ", client_name: "", start_date: "", status: "active" });
    expect(parsed).toMatchObject({ name: "Claims Portal", client_name: null, start_date: null, status: "active" });
  });

  it("rejects bad dates and short names", () => {
    const result = projectSchema.safeParse({ name: "x", start_date: "01/12/2026" });
    expect(result.success).toBe(false);
    expect(result.error?.issues.map((i) => i.path[0]).sort()).toEqual(["name", "start_date"]);
  });
});

describe("roleSchema", () => {
  it("coerces numbers from form strings and keeps defaults", () => {
    const parsed = roleSchema.parse({
      title: "DevOps Engineer",
      description: "Migrate sixty services to Kubernetes on AWS with Terraform.",
      allocation_percent: "50",
      headcount: "",
      min_experience_years: "",
    });
    expect(parsed.allocation_percent).toBe(50);
    expect(parsed.headcount).toBe(1); // an emptied field means "use the default", not 0
    expect(parsed.min_experience_years).toBeNull();
  });

  it("asks for a real description, because the AI reads it", () => {
    const result = roleSchema.safeParse({ title: "Dev", description: "Python dev" });
    expect(result.error?.issues[0]?.message).toMatch(/AI reads this text/);
  });
});

describe("requirementsSchema", () => {
  it("accepts the editor's payload", () => {
    const parsed = requirementsSchema.parse({
      seniority: "senior",
      must_have: [{ name: "Python", min_years: 5 }],
      nice_to_have: [{ name: "Celery", min_years: null }],
      min_total_years: null,
      location: null,
      domain: ["insurance"],
      search_summary: "Senior backend developer",
    });
    expect(parsed.must_have[0]).toEqual({ name: "Python", min_years: 5 });
  });

  it("rejects an unknown seniority and empty skill names", () => {
    expect(requirementsSchema.safeParse({ seniority: "guru", must_have: [], nice_to_have: [] }).success).toBe(false);
    expect(requirementsSchema.safeParse({ must_have: [{ name: "" }], nice_to_have: [] }).success).toBe(false);
  });
});

describe("matchSchema", () => {
  it("reads the checkbox and the numbers", () => {
    expect(matchSchema.parse({ top_k: "10", judge_top_n: "3", only_available: "on" })).toEqual({
      top_k: 10,
      judge_top_n: 3,
      only_available: true,
    });
    expect(matchSchema.parse({ top_k: "5", judge_top_n: "0" }).only_available).toBe(false);
  });

  it("enforces the backend's limits", () => {
    expect(matchSchema.safeParse({ top_k: "500", judge_top_n: "5" }).success).toBe(false);
    expect(matchSchema.safeParse({ top_k: "10", judge_top_n: "21" }).success).toBe(false);
  });
});

describe("formValues", () => {
  it("keeps text fields and skips files", () => {
    const form = new FormData();
    form.append("name", "x");
    form.append("file", new Blob(["a"]), "a.txt");
    expect(formValues(form)).toEqual({ name: "x" });
  });
});
