import { LoaderCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { ResumeStatus } from "@/lib/api/types";

import { isInProgress, STATUS_LABEL, STATUS_TONE } from "../labels";

/** A resume's pipeline state as a coloured label; a small spinner while the worker is on it. */
export function ResumeStatusBadge({ status }: { status: ResumeStatus }) {
  return (
    <Badge tone={STATUS_TONE[status]}>
      {isInProgress(status) && status !== "queued" && <LoaderCircle className="animate-spin" aria-hidden />}
      {STATUS_LABEL[status]}
    </Badge>
  );
}
