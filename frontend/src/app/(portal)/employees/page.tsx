import type { Metadata } from "next";
import { Suspense } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { SectionBoundary } from "@/components/section-boundary";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { IfAdmin } from "@/features/auth/components/if-admin";
import { EmployeeFilters } from "@/features/employees/components/employee-filters";
import { EmployeesTable, EmployeesTableSkeleton } from "@/features/employees/components/employees-table";
import { ImportCsv } from "@/features/employees/components/import-csv";
import { AVAILABILITY_VALUES } from "@/features/employees/labels";
import { enumParam, pageParam, textParam } from "@/lib/search-params";

export const metadata: Metadata = { title: "Employees" };

/**
 * Employees: everyone from the HR import, searchable and filterable by availability.
 * The filters live in the URL (?q=&availability=&page=), read inside <Suspense>.
 */
export default function EmployeesPage(props: PageProps<"/employees">) {
  return (
    <>
      <PageHeader title="Employees" description="Everyone in the HR import, with availability and resume status." />
      <div className="space-y-6">
        <Card>
          <CardContent className="space-y-5">
            <SectionBoundary title="The employee list">
              <Suspense
                fallback={
                  <>
                    <Skeleton className="h-16 w-full" />
                    <EmployeesTableSkeleton />
                  </>
                }
              >
                <EmployeeList searchParams={props.searchParams} />
              </Suspense>
            </SectionBoundary>
          </CardContent>
        </Card>

        <Suspense>
          <IfAdmin>
            <Card>
              <CardHeader>
                <div className="space-y-1">
                  <CardTitle>Import from HR</CardTitle>
                  <CardDescription>Create and update employees from the HR system&apos;s CSV export.</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <ImportCsv />
              </CardContent>
            </Card>
          </IfAdmin>
        </Suspense>
      </div>
    </>
  );
}

async function EmployeeList({ searchParams }: Pick<PageProps<"/employees">, "searchParams">) {
  const params = await searchParams;
  const search = textParam(params.q);
  const availability = enumParam(params.availability, AVAILABILITY_VALUES);
  const page = pageParam(params.page);
  return (
    <>
      {/* key: a new search resets the form's fields to the URL's values */}
      <EmployeeFilters key={`${search}-${availability}`} search={search} availability={availability} />
      <EmployeesTable search={search} availability={availability} page={page} />
    </>
  );
}
