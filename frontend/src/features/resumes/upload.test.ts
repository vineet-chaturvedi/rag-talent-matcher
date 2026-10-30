import { describe, expect, it } from "vitest";

import { employeeCodeFromFilename, MAX_FILE_BYTES, precheckFile, runWithConcurrency } from "./upload";

describe("employeeCodeFromFilename (same rule as the backend)", () => {
  it.each([
    ["EMP-1001_ananya_iyer.pdf", "EMP-1001"],
    ["emp-1002 rohan.docx", "EMP-1002"],
    ["EMP-1003.pdf", "EMP-1003"],
    ["_nothing.pdf", null],
  ])("%s -> %s", (name, code) => {
    expect(employeeCodeFromFilename(name)).toBe(code);
  });
});

describe("precheckFile", () => {
  it("accepts PDF and DOCX up to 10 MB", () => {
    expect(precheckFile({ name: "a.PDF", size: 1000 })).toBeNull();
    expect(precheckFile({ name: "a.docx", size: MAX_FILE_BYTES })).toBeNull();
  });

  it("explains what is wrong", () => {
    expect(precheckFile({ name: "notes.txt", size: 10 })).toMatch(/PDF and DOCX/);
    expect(precheckFile({ name: "a.pdf", size: 0 })).toMatch(/empty/);
    expect(precheckFile({ name: "a.pdf", size: MAX_FILE_BYTES + 1 })).toMatch(/10 MB/);
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
