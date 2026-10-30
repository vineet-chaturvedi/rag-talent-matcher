import { ChevronRight } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import type { ProjectRole } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

import { RoleStatusBadge } from "./role-status-badge";

/** One role in a list: title, the numbers that matter, and whether the AI has read it yet. */
export function RoleRow({ role }: { role: ProjectRole }) {
  return (
    <Link
      href={`/roles/${role.id}` as Route}
      className="flex items-center gap-3 rounded-lg px-3 py-2.5 outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/50"
    >
      <div className="min-w-0 flex-1 space-y-1">
        <p className="truncate text-sm font-medium">{role.title}</p>
        <p className="text-xs text-muted-foreground">
          {role.allocation_percent}% · {role.headcount} {role.headcount === 1 ? "person" : "people"}
          {role.location && ` · ${role.location}`}
          {role.start_date && ` · from ${formatDate(role.start_date)}`}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Badge tone={role.requirements ? "success" : "warning"}>
          {role.requirements ? "requirements ready" : "not read yet"}
        </Badge>
        <RoleStatusBadge status={role.status} />
        <ChevronRight className="size-4 text-muted-foreground" aria-hidden />
      </div>
    </Link>
  );
}
