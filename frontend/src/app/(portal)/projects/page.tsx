import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Projects & matching" };

const PLANNED = [
  "Create projects and roles; let the AI read the role description into requirements, and correct them",
  "Find best matches: ranked people with scores, matched and missing skills, availability",
  "The AI judge’s verdict per must-have, with verified quotes from the resume",
  "History of every match run",
] as const;

export default function ProjectsPage() {
  return (
    <>
      <PageHeader title="Projects & matching" description="Roles to fill, and the ranked people who could fill them." />
      <ComingSoon step={12} items={PLANNED} />
    </>
  );
}
