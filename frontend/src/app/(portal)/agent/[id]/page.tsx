import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ActionButton } from "@/components/action-button";
import { PageHeader } from "@/components/layout/page-header";
import { SectionBoundary } from "@/components/section-boundary";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { deleteConversation } from "@/features/agent/actions";
import { AgentLayout } from "@/features/agent/components/agent-layout";
import { Chat } from "@/features/agent/components/chat";
import { getConversation } from "@/features/agent/queries";
import { messagesToTurns } from "@/features/agent/transcript";
import { idParam } from "@/lib/search-params";

export const metadata: Metadata = { title: "Staffing assistant" };

/**
 * An earlier conversation: the stored questions, tool steps and answers, and the chat to continue it.
 * The agent gets the whole history again with each new question, so follow-ups like "and who of them
 * is in Pune?" work.
 */
export default async function ConversationPage(props: PageProps<"/agent/[id]">) {
  return (
    <Suspense fallback={<ConversationSkeleton />}>
      <Conversation params={props.params} />
    </Suspense>
  );
}

async function Conversation({ params }: Pick<PageProps<"/agent/[id]">, "params">) {
  const id = idParam((await params).id);
  if (id === null) notFound();
  const result = await getConversation(id);
  if (!result.ok && result.status === 404) notFound(); // not there, or not mine: same answer

  return (
    <AgentLayout activeId={id}>
      {!result.ok ? (
        <Alert>{result.message}</Alert>
      ) : (
        <SectionBoundary title="This conversation">
          <PageHeader
            title={<span className="line-clamp-1">{result.data.title}</span>}
            description="Staffing assistant"
            actions={
              <ActionButton
                action={deleteConversation.bind(null, id)}
                label="Delete"
                pendingLabel="Deleting…"
                variant="ghost"
                confirm={{
                  title: "Delete this conversation?",
                  description:
                    "Its questions and answers are removed for good. Match runs and profiles are not affected.",
                  confirmLabel: "Delete",
                }}
              />
            }
          />
          {/* key: switching conversations starts a fresh chat instead of keeping the previous one's state. */}
          <Chat key={id} conversationId={id} initialTurns={messagesToTurns(result.data.messages)} />
        </SectionBoundary>
      )}
    </AgentLayout>
  );
}

function ConversationSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-16 w-2/3 justify-self-end" />
      <Skeleton className="h-40 w-11/12" />
    </div>
  );
}
