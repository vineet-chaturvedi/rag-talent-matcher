"use client";

import { LoaderCircle, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ACCEPT_ATTRIBUTE, precheckFile } from "@/features/resumes/upload";
import { browserApi, browserErrorMessage } from "@/lib/api/browser";
import { BACKEND_UNREACHABLE } from "@/lib/api/errors";

/**
 * Upload a new resume version for ONE employee (admins). Any filename works here, because the
 * employee is known from the page. The new file becomes the current version once it is processed.
 */
export function UploadResume({ employeeId }: { employeeId: number }) {
  const router = useRouter();
  const inputId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    const problem = precheckFile(file);
    if (problem) return setMessage({ ok: false, text: problem });
    const form = event.currentTarget;
    setBusy(true);
    setMessage(null);
    try {
      const { data, error, response } = await browserApi.POST("/api/employees/{employee_id}/resumes", {
        params: { path: { employee_id: employeeId } },
        body: { file: "" },
        bodySerializer: () => {
          const body = new FormData();
          body.append("file", file);
          return body;
        },
      });
      if (data) {
        setMessage({ ok: true, text: "Uploaded. It is queued for processing." });
        setFile(null);
        form.reset();
        router.refresh();
      } else {
        setMessage({ ok: false, text: browserErrorMessage(error, response) });
      }
    } catch {
      setMessage({ ok: false, text: BACKEND_UNREACHABLE });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <Label htmlFor={inputId}>Upload a new version</Label>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          id={inputId}
          type="file"
          accept={ACCEPT_ATTRIBUTE}
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          className="max-w-xs file:mr-3 file:border-0 file:bg-transparent file:text-sm file:font-medium"
        />
        <Button type="submit" size="sm" disabled={!file || busy}>
          {busy ? <LoaderCircle className="animate-spin" aria-hidden /> : <Upload aria-hidden />}
          {busy ? "Uploading…" : "Upload"}
        </Button>
      </div>
      {message && (
        <p role="status" className={message.ok ? "text-sm text-success" : "text-sm text-destructive"}>
          {message.text}
        </p>
      )}
    </form>
  );
}
