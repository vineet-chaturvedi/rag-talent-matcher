import type { EmployeeDetail } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

import { AvailabilityBadge } from "./availability-badge";

/** The HR facts about one person (from the CSV import), as a definition list. */
export function EmployeeFacts({ employee }: { employee: EmployeeDetail }) {
  const facts: [string, string | null][] = [
    ["Department", employee.department],
    ["Location", employee.location],
    ["Manager", employee.manager_name],
    ["Email", employee.email],
    ["Joined", formatDate(employee.date_joined) || null],
    ["Current project", employee.current_project_name],
  ];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <AvailabilityBadge status={employee.availability_status} allocation={employee.allocation_percent} />
        {employee.available_from && (
          <span className="text-sm text-muted-foreground">available from {formatDate(employee.available_from)}</span>
        )}
        {!employee.is_active && <span className="text-sm text-destructive">Left the company</span>}
      </div>
      <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd>{value || "–"}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
