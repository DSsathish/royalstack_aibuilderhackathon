import { describe, expect, it } from "vitest";
import { splitSse } from "../sse";

describe("splitSse", () => {
  it("returns complete events and keeps the partial tail", () => {
    const { events, rest } = splitSse('data: {"a":1}\n\ndata: {"b":2}\n\ndata: {"c"');
    expect(events).toEqual([{ a: 1 }, { b: 2 }]);
    expect(rest).toBe('data: {"c"');
  });

  it("ignores comments and blank lines", () => {
    const { events, rest } = splitSse(': keepalive\n\n\n\ndata: {"x":"y"}\n\n');
    expect(events).toEqual([{ x: "y" }]);
    expect(rest).toBe("");
  });

  it("handles CRLF", () => {
    expect(splitSse('data: {"k":1}\r\n\r\n').events).toEqual([{ k: 1 }]);
  });

  it("keeps unicode", () => {
    expect(splitSse('data: {"t":"பால்"}\n\n').events[0]).toEqual({ t: "பால்" });
  });
});
