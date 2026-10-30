/**
 * The agent's live protocol (Step 10, app/agent/loop.py), as TypeScript.
 *
 * A streaming response can't be described by OpenAPI, so these types are written by hand. They
 * mirror what FastAPI sends, one JSON object per Server-Sent Event:
 *   data: {"type": "tool_call",   "name": "find_candidates", "arguments": {...}}
 *   data: {"type": "tool_result", "name": "find_candidates", "ok": true, "summary": "5 found: EMP-1003, ..."}
 *   data: {"type": "token",       "text": "Priya"}
 *   data: {"type": "answer",      "text": "...", "steps": 2, "tool_calls": 1, "seconds": 74.1}
 *   data: {"type": "error",       "message": "Cannot connect to Ollama"}
 */
export type AgentEvent =
  | { type: "tool_call"; name: string; arguments: Record<string, unknown> }
  | { type: "tool_result"; name: string; ok: boolean; summary: string }
  | { type: "token"; text: string }
  | { type: "answer"; text: string; steps?: number; tool_calls?: number; seconds?: number; done_reason?: string }
  | { type: "error"; message: string };

const KNOWN = new Set(["tool_call", "tool_result", "token", "answer", "error"]);

/**
 * Turns a stream of text chunks into events.
 *
 * The network delivers bytes in arbitrary pieces: one chunk may hold three events, or half of one.
 * SSE separates events with a blank line ("\n\n"), so we keep a buffer, cut off every complete
 * event, and keep the unfinished rest for the next chunk.
 *
 *   const parse = createSseParser();
 *   parse('data: {"type":"tok')        -> []                       (incomplete, kept)
 *   parse('en","text":"Hi"}\n\n')      -> [{ type: "token", text: "Hi" }]
 */
export function createSseParser(): (chunk: string) => AgentEvent[] {
  let buffer = "";
  return (chunk) => {
    buffer += chunk.replace(/\r\n/g, "\n");
    const events: AgentEvent[] = [];
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = block
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (data) {
        try {
          const event = JSON.parse(data) as AgentEvent;
          if (event && KNOWN.has(event.type)) events.push(event);
        } catch {
          // A malformed event is skipped rather than breaking the whole answer.
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
    return events;
  };
}

/** The agent's tools (app/agent/tools.py), as people would describe what it is doing. */
export const TOOL_LABEL: Record<string, string> = {
  find_candidates: "Searching for matching people",
  search_employees: "Looking up employees",
  get_employee_profile: "Reading a profile",
  check_employee_availability: "Checking availability",
  list_projects: "Listing projects and roles",
  get_match_results: "Reading saved match results",
};

export const toolLabel = (name: string) => TOOL_LABEL[name] ?? name.replace(/_/g, " ");
