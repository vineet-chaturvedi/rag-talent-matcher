import { describe, expect, it } from "vitest";

import type { AgentMessage } from "@/lib/api/types";

import { messagesToTurns } from "./transcript";

const msg = (m: Partial<AgentMessage> & Pick<AgentMessage, "id" | "role">): AgentMessage =>
  ({ content: "", tool_calls: null, tool_name: null, created_at: "2026-11-06T10:00:00", ...m }) as AgentMessage;

describe("messagesToTurns", () => {
  it("keeps the answer's message id and my rating, so a stored answer can be rated", () => {
    const turns = messagesToTurns([
      msg({ id: 1, role: "user", content: "find me a WordPress developer" }),
      msg({
        id: 2,
        role: "assistant",
        tool_calls: [{ name: "find_candidates", arguments: { must_have: ["WordPress"] } }],
      }),
      msg({ id: 3, role: "tool", tool_name: "find_candidates", content: "{}", summary: "1 found: EMP-1017" }),
      msg({ id: 4, role: "assistant", content: "EMP-1017 Ajay", feedback: { rating: "down", reason: "wrong_people" } }),
    ]);
    expect(turns).toHaveLength(1);
    const [turn] = turns;
    expect(turn?.messageId).toBe(4);
    expect(turn?.feedback?.reason).toBe("wrong_people");
    expect(turn?.steps[0]?.status).toBe("ok");
  });

  it("an interrupted turn has no answer id (nothing to rate)", () => {
    const turns = messagesToTurns([msg({ id: 1, role: "user", content: "hi" })]);
    expect(turns[0]?.messageId).toBeUndefined();
    expect(turns[0]?.status).toBe("stopped");
  });
});
