import { Users } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Pagination } from "@/components/pagination";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ResumeStatusBadge } from "@/features/resumes/components/resume-status-badge";
import type { AvailabilityStatus } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

import { EMPLOYEES_PAGE_SIZE, listEmployees } from "../queries";
import { AvailabilityBadge } from "./availability-badge";

export async function EmployeesTable({
  search,
  availability,
  page,
}: {
  search?: string;
  availability?: AvailabilityStatus;
  page: number;
}) {
  const result = await listEmployees({ search, availability, page });
  if (!result.ok) return <Alert>{result.message}</Alert>;

  const rows = result.data.slice(0, EMPLOYEES_PAGE_SIZE);
  const hasNext = result.data.length > EMPLOYEES_PAGE_SIZE;

  if (rows.length === 0) {
    return (
      <EmptyState icon={Users} title={search || availability ? "Nobody matches these filters" : "No employees yet"}>
        {search || availability
          ? "Try a shorter search or another availability."
          : "Admins: import the HR CSV with the box below."}
      </EmptyState>
    );
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Employee</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Availability</TableHead>
            <TableHead>Resume</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((employee) => (
            <TableRow key={employee.id} className={employee.is_active ? undefined : "opacity-60"}>
              <TableCell>
                <Link href={`/employees/${employee.id}` as Route} className="font-medium hover:underline">
                  {employee.full_name}
                </Link>
                <span className="block text-xs text-muted-foreground">
                  {employee.employee_code}
                  {!employee.is_active && " · left the company"}
                </span>
              </TableCell>
              <TableCell>
                {employee.designation ?? "–"}
                {employee.department && (
                  <span className="block text-xs text-muted-foreground">{employee.department}</span>
                )}
              </TableCell>
              <TableCell>{employee.location ?? "–"}</TableCell>
              <TableCell>
                <AvailabilityBadge status={employee.availability_status} allocation={employee.allocation_percent} />
                {employee.available_from && employee.availability_status !== "available" && (
                  <span className="mt-1 block text-xs text-muted-foreground">
                    from {formatDate(employee.available_from)}
                  </span>
                )}
              </TableCell>
              <TableCell>
                {employee.current_resume ? (
                  <ResumeStatusBadge status={employee.current_resume.status} />
                ) : (
                  <span className="text-xs text-muted-foreground">none</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Pagination pathname="/employees" params={{ q: search, availability }} page={page} hasNext={hasNext} />
    </>
  );
}

export function EmployeesTableSkeleton() {
  return (
    <div className="space-y-3" role="status" aria-label="Loading employees">
      {Array.from({ length: 10 }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}
