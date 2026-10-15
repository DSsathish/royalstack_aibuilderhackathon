# LLD: Live voice (speech-to-speech)

Real-time conversation on the Gemini Live API: microphone audio streams up a websocket, the model's voice streams back, the shopper can interrupt, and our existing tools run on each function call. The record-transcribe-answer loop stays as the fallback.

Verified 16 Oct: `gemini-live-2.5-flash` on Vertex AI `global` answers with streamed audio in ~3.7 s.

---

## `app/agent/live.py`

**Responsibility.** Bridge one browser websocket to one Gemini Live session: audio in, audio out, tool calls executed locally, UI actions forwarded.

**Functions.**
- `declarations(mode) -> list[types.FunctionDeclaration]` — built from `TOOLS_BY_MODE[mode]` by inspecting each function's signature and docstring, skipping the `tool_context` parameter. Only `str`, `int`, `float`, `bool` parameters exist.
- `dispatch(name, args, state) -> dict` — runs the tool with a `LiveToolContext(state)` shim (the tools only read `.state`). Unknown tool → `{"error": "unknown_tool"}`.
- `async run(ws: WebSocket, session: Session)` — opens `client.aio.live.connect(model=settings.gemini_live_model, config)` with system instruction `prompts.for_mode(mode)` plus a short voice block (short spoken sentences, confirm actions), tools from `declarations`, `response_modalities=["AUDIO"]`, input and output transcription on. Two tasks:
  - **uplink**: browser frames → binary = PCM16 16 kHz → `send_realtime_input(audio=Blob)`; JSON `{"type":"text","text"}` → `send_client_content(turn_complete=True)`; JSON `{"type":"end"}` closes.
  - **downlink**: model messages → audio parts as binary frames (PCM16 24 kHz); `input_transcription`/`output_transcription` → `{"type":"transcript","role","text"}`; `interrupted` → `{"type":"interrupted"}`; `turn_complete` → `{"type":"turn_complete"}`; `tool_call` → run each via `dispatch`, send `{"type":"action", name, data}` to the browser (same action names as the SSE chat), then `send_tool_response`.

**Frame protocol (browser ⇄ API).** Binary frames are raw PCM16 mono: 16 kHz up, 24 kHz down. Text frames are JSON with a `type`.

**Config.** `gemini_live_model: str = "gemini-live-2.5-flash"`.

## `app/api/agent.py`

`WS /agent/live?session_id=<hex>` — validates the session (404 → close code 4404), then `live.run`. Owner mode allowed in dev/test only, as for `/sessions`.

Cloud Run: websockets are supported; request timeout raised to 3600 s for the service.

## Frontend `components/LiveVoice.tsx` + `public/pcm-worklet.js`

- Button "Talk live" in the chat header area. On start: `getUserMedia({audio: {echoCancellation, noiseSuppression}})`, `AudioContext`, an `AudioWorkletNode` that downsamples the mic to 16 kHz PCM16 and posts 100 ms chunks; websocket to `/agent/live`; binary frames sent as they arrive.
- Playback: a second `AudioContext` at 24 kHz; incoming PCM16 frames become `AudioBuffer`s scheduled back to back; `interrupted` clears the queue and stops scheduled sources.
- Transcripts are pushed into the chat as user and assistant messages; `action` frames reuse the chat's existing handlers (cards, map, cart, checkout).
- States shown: connecting, listening, speaking. Stop button closes the socket and releases the mic.
- Fallback: if `AudioWorklet` or websockets are unavailable, the button is hidden and the old voice loop remains.

## Tests

- `test_live.py`: `declarations("instore")` has the right names, no `tool_context` parameter, correct types and required lists; `dispatch` runs `search_products` against the emulator and returns the compact rows; unknown tool returns an error. Websocket endpoint rejects a bad session with close code 4404 (no model connection needed).
- `test_live_live.py` (LIVE_GEMINI=1): opens the websocket with the TestClient, sends `{"type":"text","text":"Where is Aashirvaad atta?"}`, expects audio bytes, an assistant transcript, `show_products` and `highlight_map` actions.

## Rulings

- Direct `google-genai` Live API rather than ADK `run_live`: fewer moving parts, and the tools are plain functions anyway.
- Text frames are accepted on the live socket so the same session can be tested and typed into without a microphone.
- Browser echo cancellation is relied on to stop the model hearing itself; no server-side AEC.

## Findings during implementation

- `session.receive()` in google-genai yields one model turn and stops at `turn_complete`; the connection stays open. The downlink must loop over `receive()` forever. Missing this made the session end after the first tool call.
- Tool latency is on the critical path: the first query embedding took 12 s cold (client and auth), and retries on 429/503 could add 12 s more. Query embeddings now time out at 2.5 s with no retry and fall back to keyword search; the API warms the client at startup.
- Production round trip through Cloud Run (16 Oct): connected 0.2 s, ready 1.8 s, spoken answer with `show_products` action at 6.7 s.
- Cloud Run request timeout raised to 3600 s for websocket sessions.
