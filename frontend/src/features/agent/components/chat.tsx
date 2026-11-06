"use client";

import { Bot, Send, Square } from "lucide-react";
import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { BACKEND_UNREACHABLE, messageFromDetail } from "@/lib/api/errors";

import { createConversation, refreshConversations } from "../actions";
import { type AgentEvent, createSseParser, toolLabel } from "../events";
import type { Turn } from "../transcript";
import { TurnView } from "./turn-view";

const SUGGESTIONS = [
  "Who could lead a Kubernetes migration on AWS starting 1 December?",
  "Find a senior Django developer in Pune who is free at least 50%.",
  "Show me Priya Nair's profile and when she is available.",
];

/**
 * The staffing assistant (Step 13). Everything interactive lives here; the page around it is a
 * Server Component that loads the stored conversation.
 *
 * Sending a question:
 *   1. (first question only) a Server Action creates the conversation; the URL becomes /agent/{id}
 *      without a reload (history.replaceState, which Next.js keeps in sync with its router);
 *   2. POST /bff/agent/{id} with the question; the Route Handler streams FastAPI's events back;
 *   3. each event updates the current turn: tool_call adds a step, tool_result completes it, token
 *      grows the answer, answer finishes the turn, error explains what failed;
 *   4. Stop aborts the request (the relay then stops FastAPI's agent too).
 */
export function Chat({ conversationId, initialTurns }: { conversationId: number | null; initialTurns: Turn[] }) {
  const [turns, setTurns] = useState<Turn[]>(initialTurns);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const idRef = useRef<number | null>(conversationId);
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Keep the newest text in view while it streams, unless the person scrolled up to read.
  useEffect(() => {
    const end = endRef.current;
    if (!end) return;
    const nearBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight - 200;
    if (nearBottom) end.scrollIntoView({ block: "end" });
  }, [turns]);

  // Stop streaming if the person leaves the page.
  useEffect(() => () => abortRef.current?.abort(), []);

  const updateLast = (patch: (turn: Turn) => Turn) =>
    setTurns((current) => current.map((t, i) => (i === current.length - 1 ? patch(t) : t)));

  function apply(event: AgentEvent) {
    updateLast((turn) => {
      switch (event.type) {
        case "tool_call":
          setAnnouncement(`${toolLabel(event.name)}…`);
          // Text streamed before a tool call is the model "thinking aloud": the real answer comes later.
          return {
            ...turn,
            answer: "",
            steps: [...turn.steps, { name: event.name, arguments: event.arguments ?? {}, status: "running" }],
          };
        case "tool_result": {
          const steps = [...turn.steps];
          const index = steps.findLastIndex((s) => s.name === event.name && s.status === "running");
          if (index !== -1)
            steps[index] = { ...steps[index]!, status: event.ok ? "ok" : "failed", summary: event.summary };
          return { ...turn, steps };
        }
        case "token":
          return { ...turn, answer: turn.answer + event.text };
        case "answer":
          setAnnouncement("The answer is ready.");
          return {
            ...turn,
            answer: event.text || turn.answer,
            status: "done",
            seconds: event.seconds,
            messageId: event.message_id ?? undefined,
          };
        case "error":
          setAnnouncement("The assistant could not answer.");
          return { ...turn, status: "error", error: event.message };
      }
    });
  }

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    setBusy(true);
    setInput("");
    setTurns((current) => [
      ...current,
      { id: `live-${Date.now()}`, question: text, steps: [], answer: "", status: "streaming" },
    ]);
    setAnnouncement("The assistant is working on your question.");

    try {
      if (idRef.current === null) {
        const created = await createConversation(text);
        if ("error" in created) {
          updateLast((t) => ({ ...t, status: "error", error: created.error }));
          return;
        }
        idRef.current = created.id;
        window.history.replaceState(null, "", `/agent/${created.id}`);
      }

      const controller = new AbortController();
      abortRef.current = controller;
      const response = await fetch(`/bff/agent/${idRef.current}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        if (response.status === 401) {
          // A full page load on purpose: /auth/session-expired is a Route Handler (it deletes the cookie,
          // then redirects to the login page); router.push() would try to render it as a page.
          // eslint-disable-next-line @next/next/no-location-assign-relative-destination
          window.location.assign("/auth/session-expired");
          return;
        }
        const payload: unknown = await response.json().catch(() => null);
        updateLast((t) => ({ ...t, status: "error", error: messageFromDetail(payload, response.status) }));
        return;
      }

      const parse = createSseParser();
      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        for (const event of parse(value)) apply(event);
      }
      // The stream ended without an "answer" or "error" event: the connection dropped.
      updateLast((t) =>
        t.status === "streaming"
          ? { ...t, status: "error", error: "The connection ended before the answer finished." }
          : t,
      );
    } catch (error) {
      const aborted = error instanceof DOMException && error.name === "AbortError";
      updateLast((t) =>
        t.status !== "streaming"
          ? t
          : aborted
            ? { ...t, status: "stopped", error: "Stopped. Ask again to get a full answer." }
            : { ...t, status: "error", error: BACKEND_UNREACHABLE },
      );
    } finally {
      abortRef.current = null;
      setBusy(false);
      inputRef.current?.focus();
      void refreshConversations(); // the sidebar: new title, newest first
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void ask(input);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter makes a new line; not while an input method is composing (e.g. Hindi, Japanese).
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void ask(input);
    }
  }

  return (
    <div className="flex min-h-[calc(100dvh-10rem)] flex-col">
      <p className="sr-only" role="status" aria-live="polite">
        {announcement}
      </p>

      <div className="flex-1 space-y-6 pb-6">
        {turns.length === 0 ? (
          <div className="flex flex-col items-center gap-4 py-12 text-center">
            <span className="flex size-12 items-center justify-center rounded-full bg-accent text-accent-foreground">
              <Bot className="size-6" aria-hidden />
            </span>
            <div className="space-y-1">
              <p className="font-medium">Ask about people, skills, availability or projects</p>
              <p className="max-w-md text-sm text-muted-foreground">
                The assistant searches the knowledge base with its tools and shows each step. It reads data; it never
                changes anything.
              </p>
            </div>
            <ul className="flex w-full max-w-lg flex-col gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <li key={suggestion}>
                  <Button
                    variant="outline"
                    className="h-auto w-full justify-start py-2.5 text-left whitespace-normal"
                    onClick={() => void ask(suggestion)}
                    disabled={busy}
                  >
                    {suggestion}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          turns.map((turn) => <TurnView key={turn.id} turn={turn} />)
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={onSubmit}
        className="sticky bottom-0 -mx-1 border-t bg-background/95 px-1 pt-3 pb-4 backdrop-blur supports-[backdrop-filter]:bg-background/80"
      >
        <label htmlFor="agent-question" className="sr-only">
          Your question
        </label>
        <div className="flex items-end gap-2">
          <Textarea
            ref={inputRef}
            id="agent-question"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
            maxLength={4000}
            placeholder="e.g. Who knows Terraform and can start in December?"
            className="min-h-11 resize-none"
            autoFocus
          />
          {busy ? (
            <Button type="button" variant="outline" onClick={() => abortRef.current?.abort()} aria-label="Stop">
              <Square aria-hidden /> Stop
            </Button>
          ) : (
            <Button type="submit" disabled={!input.trim()} aria-label="Send">
              <Send aria-hidden /> Send
            </Button>
          )}
        </div>
        <p className="mt-1.5 text-xs text-muted-foreground">
          Enter to send, Shift+Enter for a new line. On a CPU an answer can take a minute or two; the steps show
          progress.
        </p>
      </form>
    </div>
  );
}
