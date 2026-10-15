/** Server-Sent Events parsing. Pure function plus an async iterator over a fetch body. */

export type UiEvent =
  | { type: "status"; tool: string }
  | { type: "action"; name: string; data: Record<string, unknown> }
  | { type: "token"; text: string }
  | { type: "done"; text: string }
  | { type: "transcript"; text: string }
  | { type: "error"; text: string };

export function splitSse(buffer: string): { events: unknown[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const chunks = normalized.split("\n\n");
  const rest = chunks.pop() ?? "";
  const events: unknown[] = [];
  for (const chunk of chunks) {
    const data = chunk
      .split("\n")
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).trim())
      .join("\n");
    if (data) events.push(JSON.parse(data));
  }
  return { events, rest };
}

export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<UiEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = splitSse(buffer);
    buffer = rest;
    for (const e of events) yield e as UiEvent;
  }
}
