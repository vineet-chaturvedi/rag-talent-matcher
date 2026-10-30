"use client";

import { FileSpreadsheet, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useId, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { browserApi, browserErrorMessage } from "@/lib/api/browser";
import { BACKEND_UNREACHABLE } from "@/lib/api/errors";
import type { EmployeeImportResult } from "@/lib/api/types";
import { plural } from "@/lib/utils";

const MAX_CSV_BYTES = 5 * 1024 * 1024; // the backend's limit

/**
 * Import the HR export (CSV) - admins. Creates new employees and updates existing ones by
 * employee_code; rows with problems are listed with their line number, the rest still import.
 * The file goes straight from the browser to FastAPI through the /api rewrite (see lib/api/browser.ts).
 */
export function ImportCsv() {
  const router = useRouter();
  const inputId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<EmployeeImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    if (file.size > MAX_CSV_BYTES) return setError("The CSV is larger than 5 MB.");
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const {
        data,
        error: apiError,
        response,
      } = await browserApi.POST("/api/employees/import", {
        body: { file: "" },
        bodySerializer: () => {
          const form = new FormData();
          form.append("file", file);
          return form;
        },
      });
      if (data) {
        setResult(data);
        router.refresh(); // the list above shows the new and updated people
      } else {
        setError(browserErrorMessage(apiError, response));
      }
    } catch {
      setError(BACKEND_UNREACHABLE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-56 flex-1 space-y-1.5">
          <Label htmlFor={inputId}>HR export (CSV, UTF-8)</Label>
          <Input
            id={inputId}
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="file:mr-3 file:border-0 file:bg-transparent file:text-sm file:font-medium"
          />
        </div>
        <Button type="submit" disabled={!file || busy}>
          {busy ? <LoaderCircle className="animate-spin" aria-hidden /> : <FileSpreadsheet aria-hidden />}
          {busy ? "Importing…" : "Import"}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Required columns: <code>employee_code</code>, <code>full_name</code>. Existing employees are updated by code.
      </p>
      {error && <Alert>{error}</Alert>}
      {result && (
        <Alert tone={result.failed ? "warning" : "info"} title="Import finished">
          {plural(result.created, "employee")} created, {result.updated} updated
          {result.failed ? `, ${plural(result.failed, "row")} skipped:` : "."}
          {result.errors.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-5">
              {result.errors.slice(0, 20).map((row) => (
                <li key={`${row.line}-${row.employee_code}`}>
                  Line {row.line}
                  {row.employee_code ? ` (${row.employee_code})` : ""}: {row.message}
                </li>
              ))}
              {result.errors.length > 20 && <li>… and {result.errors.length - 20} more</li>}
            </ul>
          )}
        </Alert>
      )}
    </form>
  );
}
