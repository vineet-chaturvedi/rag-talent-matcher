import type { Metadata } from "next";

import { ComingSoon } from "@/components/coming-soon";
import { PageHeader } from "@/components/layout/page-header";

export const metadata: Metadata = { title: "Staffing assistant" };

const PLANNED = [
  "Chat with the AI agent: “Who could join a Kubernetes migration from 1 December?”",
  "See each step live: which tool it used and what it found",
  "Answers stream in word by word; earlier conversations are kept",
] as const;

export default function AgentPage() {
  return (
    <>
      <PageHeader
        title="Staffing assistant"
        description="Ask the AI agent in plain language; it searches, checks availability and explains."
      />
      <ComingSoon step={13} items={PLANNED} />
    </>
  );
}
