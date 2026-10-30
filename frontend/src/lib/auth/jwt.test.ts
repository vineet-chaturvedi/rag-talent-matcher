import { describe, expect, it } from "vitest";

import { isTokenExpired, readTokenExpiry } from "./jwt";

/** Build an unsigned JWT-shaped string: header.payload.signature (base64url, no padding). */
function fakeJwt(payload: object): string {
  const b64url = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${b64url({ alg: "HS256", typ: "JWT" })}.${b64url(payload)}.signature`;
}

describe("readTokenExpiry", () => {
  it("returns exp in milliseconds", () => {
    expect(readTokenExpiry(fakeJwt({ sub: "1", exp: 1_800_000_000 }))).toBe(1_800_000_000_000);
  });

  it("returns null for tokens without a numeric exp", () => {
    expect(readTokenExpiry(fakeJwt({ sub: "1" }))).toBeNull();
    expect(readTokenExpiry(fakeJwt({ exp: "tomorrow" }))).toBeNull();
  });

  it("returns null for garbage instead of throwing", () => {
    expect(readTokenExpiry("not-a-jwt")).toBeNull();
    expect(readTokenExpiry("a.%%%.c")).toBeNull();
    expect(readTokenExpiry("")).toBeNull();
  });
});

describe("isTokenExpired", () => {
  const now = 1_800_000_000_000;

  it("treats a missing token as expired", () => {
    expect(isTokenExpired(undefined, now)).toBe(true);
  });

  it("accepts a token that expires in the future", () => {
    expect(isTokenExpired(fakeJwt({ exp: now / 1000 + 3600 }), now)).toBe(false);
  });

  it("rejects a token past its expiry, with a few seconds of slack", () => {
    expect(isTokenExpired(fakeJwt({ exp: now / 1000 - 1 }), now)).toBe(true);
    expect(isTokenExpired(fakeJwt({ exp: now / 1000 + 2 }), now)).toBe(true); // inside the 5 s skew
  });
});
