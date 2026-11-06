import { Download, ExternalLink } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import type { Resume } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type FileInfo = Pick<Resume, "id" | "mime_type" | "original_filename">;

/** Where the original file of a resume version is served (the /bff relay adds the login token). */
export function resumeFileUrl(resumeId: number, download = false): string {
  return `/bff/resumes/${resumeId}/file${download ? "?download=1" : ""}`;
}

export function isPdf(resume: Pick<Resume, "mime_type">): boolean {
  return resume.mime_type === "application/pdf";
}

/**
 * "Open" (PDFs, in a new tab, in the browser's own viewer) and "Download" for the ORIGINAL file of one
 * resume version. Word files only get "Download": browsers can't display .docx/.doc.
 * Admins only: wrap in <IfAdmin> (FastAPI refuses others with 403 anyway).
 */
export function ResumeFileLinks({ resume, size = "sm" }: { resume: FileInfo; size?: "sm" | "default" }) {
  const style = cn(buttonVariants({ variant: "outline", size }));
  return (
    <>
      {isPdf(resume) && (
        <a
          href={resumeFileUrl(resume.id)}
          target="_blank"
          rel="noopener noreferrer"
          className={style}
          aria-label={`Open ${resume.original_filename} in a new tab`}
        >
          <ExternalLink aria-hidden /> Open
        </a>
      )}
      <a
        href={resumeFileUrl(resume.id, true)}
        download={resume.original_filename}
        className={style}
        aria-label={`Download ${resume.original_filename}`}
      >
        <Download aria-hidden /> Download
      </a>
    </>
  );
}
