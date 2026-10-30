import { MessageSquare, Plus } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert } from "@/components/ui/alert";
import { cn, formatDateTime } from "@/lib/utils";

import { listConversations } from "../queries";

/**
 * The left column of the assistant: "New conversation" and my earlier conversations, newest first.
 * A Server Component: the list is fetched on the server with my session, so it is only ever MINE
 * (FastAPI filters by the token's user). After each answer the chat calls refresh(), and this
 * re-renders with the new title and order.
 */
export async function ConversationList({ activeId }: { activeId: number | null }) {
  const result = await listConversations();
  return (
    <nav aria-label="Conversations" className="space-y-3">
      <Button asChild variant={activeId === null ? "default" : "outline"} className="w-full justify-start">
        <Link href="/agent">
          <Plus aria-hidden /> New conversation
        </Link>
      </Button>
      {!result.ok ? (
        <Alert>{result.message}</Alert>
      ) : result.data.length === 0 ? (
        <p className="px-1 text-xs text-muted-foreground">Your conversations will be listed here.</p>
      ) : (
        <ul className="space-y-0.5">
          {result.data.map((c) => (
            <li key={c.id}>
              <Link
                href={`/agent/${c.id}` as Route}
                aria-current={c.id === activeId ? "page" : undefined}
                className={cn(
                  "flex items-start gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent",
                  c.id === activeId && "bg-accent font-medium text-accent-foreground",
                )}
              >
                <MessageSquare className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden />
                <span className="min-w-0">
                  <span className="line-clamp-2">{c.title}</span>
                  <span className="block text-xs font-normal text-muted-foreground">
                    {formatDateTime(c.updated_at)}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}

export function ConversationListSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-9 w-full" />
      {Array.from({ length: 4 }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}
