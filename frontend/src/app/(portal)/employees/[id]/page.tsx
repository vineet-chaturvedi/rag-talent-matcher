import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { SectionBoundary } from "@/components/section-boundary";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { IfAdmin } from "@/features/auth/components/if-admin";
import { EmployeeFacts } from "@/features/employees/components/employee-header";
import { ProfileSections, ProfileSkeleton } from "@/features/employees/components/profile-sections";
import { ResumeHistory } from "@/features/employees/components/resume-history";
import { getEmployee } from "@/features/employees/queries";
import { ResumeFileLinks } from "@/features/resumes/components/resume-file-links";
import { idParam } from "@/lib/search-params";

export const metadata: Metadata = { title: "Employee" };

/**
 * One employee: HR facts, the AI profile of the current resume (with evidence), every resume version.
 * Admins can open or download the original file of the current resume (header) and of every version.
 * The id comes from the URL (/employees/7); a bad or unknown id shows the 404 page.
 */
export default function EmployeePage(props: PageProps<"/employees/[id]">) {
  return (
    <>
      <Link
        href="/employees"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" aria-hidden /> Employees
      </Link>
      <SectionBoundary title="This employee">
        <Suspense fallback={<EmployeeSkeleton />}>
          <Employee params={props.params} />
        </Suspense>
      </SectionBoundary>
    </>
  );
}

async function Employee({ params }: Pick<PageProps<"/employees/[id]">, "params">) {
  const id = idParam((await params).id);
  if (id === null) notFound();
  const result = await getEmployee(id);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <Alert>{result.message}</Alert>;
  }
  const employee = result.data;
  const current = employee.resumes.find((r) => r.is_current);

  return (
    <>
      <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold tracking-tight">{employee.full_name}</h1>
          <p className="text-sm text-muted-foreground">
            {employee.employee_code}
            {employee.designation && ` · ${employee.designation}`}
          </p>
        </div>
        {current && (
          <Suspense>
            <IfAdmin>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-muted-foreground">Current resume:</span>
                <ResumeFileLinks resume={current} />
              </div>
            </IfAdmin>
          </Suspense>
        )}
      </header>
      <div className="space-y-6">
        <Card>
          <CardContent>
            <EmployeeFacts employee={employee} />
          </CardContent>
        </Card>
        <div className="grid items-start gap-6 lg:grid-cols-[1fr_22rem]">
          <SectionBoundary title="The AI profile">
            <Suspense fallback={<ProfileSkeleton />}>
              <ProfileSections resume={current} />
            </Suspense>
          </SectionBoundary>
          <ResumeHistory employeeId={employee.id} resumes={employee.resumes} />
        </div>
      </div>
    </>
  );
}

function EmployeeSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading the employee">
      <Skeleton className="h-12 w-72" />
      <Skeleton className="h-32 w-full rounded-xl" />
      <Skeleton className="h-96 w-full rounded-xl" />
    </div>
  );
}
