import { Badge } from "@/components/ui/badge";
import type { RoleStatus } from "@/lib/api/types";

import { ROLE_STATUS } from "../labels";

export function RoleStatusBadge({ status }: { status: RoleStatus }) {
  return <Badge tone={ROLE_STATUS[status].tone}>{ROLE_STATUS[status].label}</Badge>;
}
