/**
 * Pure helpers for resume uploads, shared by the bulk upload box and the per-employee upload.
 * No React and no network here, so they are unit tested (upload.test.ts).
 */

export const MAX_FILE_MB = 25; // must match the backend's MAX_UPLOAD_MB (Word files with embedded fonts reach 12+ MB)
export const MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024;
export const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".doc"] as const;
export const ACCEPT_ATTRIBUTE =
  ".pdf,.docx,.doc,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword";

/**
 * "EMP-1001_ananya_iyer.pdf" -> "EMP-1001", like the backend: everything before the first "_", space or ".".
 * Only a code with a digit counts: "Rajendra - Full Stack.pdf" has no code (the backend then matches the
 * employee's name instead).
 */
export function employeeCodeFromFilename(filename: string): string | null {
  const match = /^([^_\s.]+)/.exec(filename);
  const code = match?.[1]?.toUpperCase();
  return code && /\d/.test(code) ? code : null;
}

/**
 * Problems we can see BEFORE uploading (saves a round trip and tells the person at once).
 * The backend checks everything again, including the file's real content ("magic bytes").
 */
export function precheckFile(file: { name: string; size: number }): string | null {
  const name = file.name.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))) return "Only PDF, DOCX and DOC files are accepted.";
  if (file.size === 0) return "The file is empty.";
  if (file.size > MAX_FILE_BYTES) return `Larger than ${MAX_FILE_MB} MB.`;
  return null;
}

/**
 * Run `worker` over `items` with at most `limit` running at the same time.
 * Why not all at once: 200 parallel uploads would flood the browser, Next.js and FastAPI. Why not one
 * by one: a small amount of parallelism (2-3) uses the network well while each file still gets its
 * own clear result.
 */
export async function runWithConcurrency<T>(
  items: readonly T[],
  limit: number,
  worker: (item: T, index: number) => Promise<void>,
) {
  let next = 0;
  const lanes = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const index = next++;
      await worker(items[index] as T, index);
    }
  });
  await Promise.all(lanes);
}
