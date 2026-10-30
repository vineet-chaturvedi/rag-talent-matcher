import { Badge } from "@/components/ui/badge";
import type { AvailabilityStatus } from "@/lib/api/types";

import { AVAILABILITY_LABEL, AVAILABILITY_TONE } from "../labels";

export function AvailabilityBadge({ status, allocation }: { status: AvailabilityStatus; allocation?: number }) {
  return (
    <Badge tone={AVAILABILITY_TONE[status]}>
      {AVAILABILITY_LABEL[status]}
      {status === "partial" && allocation !== undefined ? ` · ${allocation}%` : ""}
    </Badge>
  );
}
