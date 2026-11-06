import { describe, expect, it } from "vitest";

import { isPdf, resumeFileUrl } from "./components/resume-file-links";

describe("resume file links", () => {
  it("builds the relay URL, with ?download=1 only when asked", () => {
    expect(resumeFileUrl(16)).toBe("/bff/resumes/16/file");
    expect(resumeFileUrl(16, true)).toBe("/bff/resumes/16/file?download=1");
  });

  it("only PDFs can be opened in the browser", () => {
    expect(isPdf({ mime_type: "application/pdf" })).toBe(true);
    expect(isPdf({ mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })).toBe(false);
    expect(isPdf({ mime_type: "application/msword" })).toBe(false);
  });
});
