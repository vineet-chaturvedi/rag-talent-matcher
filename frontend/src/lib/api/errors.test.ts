import { describe, expect, it } from "vitest";

import { BACKEND_UNREACHABLE, fallbackMessage, messageFromDetail } from "./errors";

describe("messageFromDetail", () => {
  it("uses FastAPI's string detail", () => {
    expect(messageFromDetail({ detail: "Wrong email or password." }, 401)).toBe("Wrong email or password.");
  });

  it("joins validation errors (422) with the field name, without the 'body' prefix", () => {
    const payload = {
      detail: [
        { loc: ["body", "email"], msg: "Field required", type: "missing" },
        { loc: ["query", "limit"], msg: "Input should be less than or equal to 500", type: "less_than_equal" },
      ],
    };
    expect(messageFromDetail(payload, 422)).toBe(
      "email: Field required; query.limit: Input should be less than or equal to 500",
    );
  });

  it("falls back to a message for the status when there is no usable detail", () => {
    expect(messageFromDetail(null, 500)).toBe(fallbackMessage(500));
    expect(messageFromDetail({ detail: "" }, 404)).toBe(fallbackMessage(404));
    expect(messageFromDetail("<html>Bad gateway</html>", 502)).toBe(fallbackMessage(502));
  });
});

describe("fallbackMessage", () => {
  it("explains an unreachable backend", () => {
    expect(fallbackMessage(0)).toBe(BACKEND_UNREACHABLE);
  });

  it("has a specific text for common statuses", () => {
    expect(fallbackMessage(403)).toMatch(/permission/);
    expect(fallbackMessage(429)).toMatch(/Too many/);
    expect(fallbackMessage(418)).toBe("The request failed (HTTP 418).");
  });
});
