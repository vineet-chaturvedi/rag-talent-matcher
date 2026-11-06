import { LoaderCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { ResumeStatus } from "@/lib/api/types";

import { isInProgress, STATUS_LABEL, STATUS_TONE } from "../labels";

/**
 * A resume's pipeline state as a coloured label; a small spinner while the worker is on it.
 * Pass isCurrent: an older version that finished processing is kept as history but is no longer in the
 * search indexes, so it must not say "Searchable".
 */
export function ResumeStatusBadge({ status, isCurrent = true }: { status: ResumeStatus; isCurrent?: boolean }) {
  if (status === "ready" && !isCurrent) return <Badge tone="neutral">Older version · not searched</Badge>;
  return (
    <Badge tone={STATUS_TONE[status]}>
      {isInProgress(status) && status !== "queued" && <LoaderCircle className="animate-spin" aria-hidden />}
      {STATUS_LABEL[status]}
    </Badge>
  );
}
