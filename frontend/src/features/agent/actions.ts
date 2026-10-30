"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";

import { request } from "@/lib/api/client";

/**
 * Conversation housekeeping (Step 13). Asking a question is NOT a Server Action: the answer streams
 * for up to minutes, which is what the /bff/agent Route Handler is for.
 */

/** Start a conversation; returns its id so the chat can stream the first question into it. */
export async function createConversation(title: string): Promise<{ id: number } | { error: string }> {
  const result = await request((api) =>
    api.POST("/api/agent/conversations", { body: { title: title.trim().slice(0, 80) || null } }),
  );
  return result.ok ? { id: result.data.id } : { error: result.message };
}

export async function deleteConversation(conversationId: number): Promise<{ ok: boolean; message: string }> {
  if (!Number.isInteger(conversationId) || conversationId <= 0) return { ok: false, message: "Invalid." };
  const result = await request((api) =>
    api.DELETE("/api/agent/conversations/{conversation_id}", {
      params: { path: { conversation_id: conversationId } },
    }),
  );
  if (!result.ok) return { ok: false, message: result.message };
  redirect("/agent");
}

/** After an answer: re-render the page's server parts, so the sidebar shows the new title and order. */
export async function refreshConversations(): Promise<void> {
  refresh();
}
