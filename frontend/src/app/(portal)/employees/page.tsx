import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Employees" };

const PLANNED = [
  "Search and browse employees with availability",
  "Profile page: skills with years and last used, jobs, certifications, extracted by the AI",
  "Admins: import the HR CSV",
] as const;

export default function EmployeesPage() {
  return (
    <>
      <PageHeader title="Employees" description="Everyone in the HR import, with their AI-extracted profile." />
      <ComingSoon step={12} items={PLANNED} />
    </>
  );
}
