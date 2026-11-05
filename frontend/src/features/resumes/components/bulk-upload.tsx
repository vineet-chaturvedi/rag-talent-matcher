"use client";

import { CircleCheck, CircleX, LoaderCircle, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { type DragEvent, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { browserApi, browserErrorMessage } from "@/lib/api/browser";
import { BACKEND_UNREACHABLE } from "@/lib/api/errors";
import { cn, formatBytes, plural } from "@/lib/utils";

import { ACCEPT_ATTRIBUTE, employeeCodeFromFilename, precheckFile, runWithConcurrency } from "../upload";

type ItemState = "waiting" | "uploading" | "done" | "failed";
type Item = { id: string; file: File; code: string | null; state: ItemState; message?: string };

/**
 * Drag-and-drop bulk upload (admins). Files are matched to employees by the code at the start of the name
 * (EMP-1001_name.pdf) or, without a code, by the employee's full name ("Rajendra - Full Stack.pdf").
 *
 * How it works:
 *   1. Files are checked in the browser first (type, size) so obvious mistakes show at once.
 *   2. Each file is POSTed on its own to /api/resumes/bulk (2 at a time), through the rewrite to
 *      FastAPI. One file per request = a clear result per file, and a failure doesn't cancel the rest.
 *   3. FastAPI stores the file and queues it; the background worker does the slow AI work later.
 *   4. When all are sent, router.refresh() re-renders the list below, which then updates itself
 *      while the worker processes them.
 */
export function BulkUpload() {
  const router = useRouter();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);

  const update = (id: string, patch: Partial<Item>) =>
    setItems((current) => current.map((item) => (item.id === id ? { ...item, ...patch } : item)));

  async function upload(files: File[]) {
    if (files.length === 0 || busy) return;
    const batch: Item[] = files.map((file, i) => {
      const problem = precheckFile(file);
      return {
        id: `${Date.now()}-${i}-${file.name}`,
        file,
        code: employeeCodeFromFilename(file.name),
        state: problem ? "failed" : "waiting",
        message: problem ?? undefined,
      };
    });
    setItems(batch);
    setBusy(true);

    await runWithConcurrency(
      batch.filter((item) => item.state === "waiting"),
      2,
      async (item) => {
        update(item.id, { state: "uploading" });
        try {
          const { data, error, response } = await browserApi.POST("/api/resumes/bulk", {
            // multipart/form-data: the browser sets the boundary header itself, so we pass FormData as is.
            body: { files: [] },
            bodySerializer: () => {
              const form = new FormData();
              form.append("files", item.file);
              return form;
            },
          });
          const result = data?.items[0];
          if (!response.ok || !result) {
            update(item.id, { state: "failed", message: browserErrorMessage(error, response) });
          } else if (!result.ok) {
            update(item.id, { state: "failed", message: result.error ?? "Rejected." });
          } else {
            update(item.id, {
              state: "done",
              code: result.employee_code ?? item.code,
              message: "Queued for processing",
            });
          }
        } catch {
          update(item.id, { state: "failed", message: BACKEND_UNREACHABLE });
        }
      },
    );

    setBusy(false);
    if (inputRef.current) inputRef.current.value = "";
    router.refresh();
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    void upload(Array.from(event.dataTransfer.files));
  }

  const done = items.filter((i) => i.state === "done").length;
  const failed = items.filter((i) => i.state === "failed").length;

  return (
    <div className="space-y-3">
      <label
        htmlFor={inputId}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors",
          "focus-within:ring-[3px] focus-within:ring-ring/50",
          dragging ? "border-primary bg-primary/5" : "border-input hover:bg-muted/50",
          busy && "pointer-events-none opacity-60",
        )}
      >
        <Upload className="size-6 text-muted-foreground" aria-hidden />
        <span className="text-sm font-medium">Drop resumes here, or click to choose files</span>
        <span className="text-xs text-muted-foreground">
          PDF, DOCX or DOC, up to 25 MB each, named after the employee code (<code>EMP-1001_name.pdf</code>) or starting
          with the employee&apos;s full name
        </span>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          multiple
          accept={ACCEPT_ATTRIBUTE}
          className="sr-only"
          disabled={busy}
          onChange={(event) => void upload(Array.from(event.target.files ?? []))}
        />
      </label>

      {items.length > 0 && (
        <div className="space-y-2">
          <p role="status" className="text-sm text-muted-foreground">
            {busy
              ? `Uploading… ${done + failed} of ${items.length}`
              : `${plural(done, "file")} uploaded${failed ? `, ${failed} failed` : ""}.`}
          </p>
          <ul className="max-h-64 divide-y overflow-y-auto rounded-lg border text-sm">
            {items.map((item) => (
              <li key={item.id} className="flex items-start gap-2 px-3 py-2">
                <StateIcon state={item.state} />
                <div className="min-w-0 flex-1">
                  <span className="block truncate">{item.file.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {item.code ?? "no code"} · {formatBytes(item.file.size)}
                    {item.message && (
                      <span className={item.state === "failed" ? "text-destructive" : undefined}>
                        {" "}
                        · {item.message}
                      </span>
                    )}
                  </span>
                </div>
              </li>
            ))}
          </ul>
          {!busy && (
            <Button variant="ghost" size="sm" onClick={() => setItems([])}>
              Clear list
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function StateIcon({ state }: { state: ItemState }) {
  if (state === "done") return <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" aria-label="Uploaded" />;
  if (state === "failed") return <CircleX className="mt-0.5 size-4 shrink-0 text-destructive" aria-label="Failed" />;
  if (state === "uploading")
    return <LoaderCircle className="mt-0.5 size-4 shrink-0 animate-spin text-primary" aria-label="Uploading" />;
  return <span className="mt-1.5 size-2 shrink-0 rounded-full bg-muted-foreground/40" aria-label="Waiting" />;
}
