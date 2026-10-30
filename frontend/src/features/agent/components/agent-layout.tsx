import { type ReactNode, Suspense } from "react";

import { SectionBoundary } from "@/components/section-boundary";

import { ConversationList, ConversationListSkeleton } from "./conversation-list";

/**
 * Both assistant pages (/agent and /agent/[id]) share this two-column frame: conversations on the left
 * (hidden on small screens, where the chat gets the whole width), the chat on the right.
 */
export function AgentLayout({ activeId, children }: { activeId: number | null; children: ReactNode }) {
  return (
    <div className="grid gap-6 lg:grid-cols-[15rem_minmax(0,1fr)]">
      <aside className="hidden lg:block">
        <div className="sticky top-20 max-h-[calc(100dvh-6rem)] overflow-y-auto pr-1">
          <SectionBoundary title="Your conversations">
            <Suspense fallback={<ConversationListSkeleton />}>
              <ConversationList activeId={activeId} />
            </Suspense>
          </SectionBoundary>
        </div>
      </aside>
      <div className="min-w-0">{children}</div>
    </div>
  );
}
