import { describe, expect, it } from "vitest";

import { employeeCodeFromFilename, MAX_FILE_BYTES, precheckFile, runWithConcurrency } from "./upload";

describe("employeeCodeFromFilename (same rule as the backend)", () => {
  it.each([
    ["EMP-1001_ananya_iyer.pdf", "EMP-1001"],
    ["emp-1002 rohan.docx", "EMP-1002"],
    ["EMP-1003.pdf", "EMP-1003"],
    ["_nothing.pdf", null],
    ["Rajendra - Full Stack.pdf", null], // no code: the backend matches the employee's name instead
  ])("%s -> %s", (name, code) => {
    expect(employeeCodeFromFilename(name)).toBe(code);
  });
});

describe("precheckFile", () => {
  it("accepts PDF, DOCX and DOC up to 25 MB", () => {
    expect(precheckFile({ name: "a.PDF", size: 1000 })).toBeNull();
    expect(precheckFile({ name: "a.docx", size: MAX_FILE_BYTES })).toBeNull();
    expect(precheckFile({ name: "old.doc", size: 1000 })).toBeNull();
  });

  it("explains what is wrong", () => {
    expect(precheckFile({ name: "notes.txt", size: 10 })).toMatch(/PDF, DOCX and DOC/);
    expect(precheckFile({ name: "a.pdf", size: 0 })).toMatch(/empty/);
    expect(precheckFile({ name: "a.pdf", size: MAX_FILE_BYTES + 1 })).toMatch(/25 MB/);
  });
});

describe("runWithConcurrency", () => {
  it("processes every item, never more than `limit` at once", async () => {
    let running = 0;
    let peak = 0;
    const done: number[] = [];
    await runWithConcurrency([1, 2, 3, 4, 5], 2, async (item) => {
      running += 1;
      peak = Math.max(peak, running);
      await new Promise((resolve) => setTimeout(resolve, 5));
      done.push(item);
      running -= 1;
    });
    expect(done.sort()).toEqual([1, 2, 3, 4, 5]);
    expect(peak).toBe(2);
  });

  it("does nothing for an empty list", async () => {
    await expect(runWithConcurrency([], 3, async () => {})).resolves.toBeUndefined();
  });
});
