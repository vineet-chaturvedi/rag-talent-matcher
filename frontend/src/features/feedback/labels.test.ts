import { describe, expect, it } from "vitest";

import { AGENT_REASONS, MATCH_REASONS, reasonLabel } from "./labels";

describe("feedback reasons", () => {
  it("has a readable label for every reason the backend accepts", () => {
    expect(reasonLabel("not_available")).toBe("Not really available");
    expect(reasonLabel("wrong_people")).toBe("Named the wrong people");
    expect(reasonLabel(null)).toBe("");
    expect(reasonLabel("future_reason")).toBe("future_reason");
  });

  it("offers each reason once, with 'other' last", () => {
    for (const list of [MATCH_REASONS, AGENT_REASONS]) {
      const values = list.map((r) => r.value);
      expect(new Set(values).size).toBe(values.length);
      expect(values.at(-1)).toBe("other");
    }
  });
});
