import type { Metadata } from "next";

import { PageHeader } from "@/components/layout/page-header";
import { AgentLayout } from "@/features/agent/components/agent-layout";
import { Chat } from "@/features/agent/components/chat";

export const metadata: Metadata = { title: "Staffing assistant" };

/**
 * A new conversation. Nothing to load, so the chat is part of the instant (prerendered) shell; the
 * conversation itself is only created when the first question is sent (no empty conversations).
 */
export default function NewConversationPage() {
  return (
    <AgentLayout activeId={null}>
      <PageHeader
        title="Staffing assistant"
        description="Ask in plain language; it searches profiles, checks availability and explains its answer."
      />
      <Chat conversationId={null} initialTurns={[]} />
    </AgentLayout>
  );
}
