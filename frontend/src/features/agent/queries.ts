import "server-only";

import { request } from "@/lib/api/client";

/** My conversations, newest first. FastAPI only ever returns the signed-in person's own. */
export const listConversations = () => request((api) => api.GET("/api/agent/conversations"));

/** One conversation with every message (questions, tool calls and results, answers). 404 = not mine. */
export const getConversation = (conversationId: number) =>
  request((api) =>
    api.GET("/api/agent/conversations/{conversation_id}", { params: { path: { conversation_id: conversationId } } }),
  );
