# LLD: Voice quality and conversation memory

Goal: the assistant behaves like a first-class voice assistant. It waits for you to finish, asks when it did not catch something, remembers the conversation whether you type or talk (and across days for owners), survives a dropped connection, and speaks in a consistent natural voice.

Verified on `gemini-live-2.5-flash` (Vertex, global) 17 Oct: prebuilt voices, tuned activity detection, session resumption, context-window compression and affective dialog are all accepted.

---

## `app/services/conversation.py` — one memory for every channel

- Turns live in Firestore under `conversations/{key}/turns/{id}` as `{role, text, at}`; `text` truncated to 600 chars; blank turns ignored.
- `key(session)`: the session id for shoppers (anonymous, visit-scoped); the owner's uid for owner sessions (memory across visits and devices).
- `add_turn(session, role, text)`, `recent(session, limit)`, `history_text(session, limit=12)` → "Earlier in this conversation (most recent last):" followed by `Shopper:`/`Owner:` and `Assistant:` lines, each cut to 160 chars, bounded to roughly 1 KB. Empty string when there is nothing.

## Text agent (`app/agent/agent.py`)

- Memory now has one source of truth: Firestore turns. Each chat turn creates a fresh ADK session whose state carries `history_text`; the instruction is a provider function that appends it to the mode prompt. The ADK in-memory session service is no longer relied on for continuity, so memory survives instance restarts and is identical for text and voice.
- After each turn `chat()` records the user text and the final assistant text.

## Live bridge (`app/agent/live.py`)

Session config:
- `speech_config`: prebuilt voice `Kore` (clear, warm; same voice every time).
- `realtime_input_config.automatic_activity_detection`: start sensitivity LOW (ignores small noises), end sensitivity LOW (waits longer before deciding you are done), `prefix_padding_ms=300`, `silence_duration_ms=900`.
- `enable_affective_dialog=True`: the model adapts tone to the speaker.
- `context_window_compression` sliding window: long conversations never hit the context limit.
- `session_resumption`: the server issues handles; the bridge keeps the latest per session and reconnects with it so a network drop resumes the same conversation. `MAX_SESSION_S` raised to 1800.
- `system_instruction` = mode prompt + voice block + `history_text`.

Voice block additions: "If you did not clearly hear or understand, say what you heard and ask the shopper to repeat. Never guess a product name." and "Keep answers to one or two sentences; let the shopper interrupt."

Transcripts: a `TurnRecorder` accumulates input and output transcription chunks; on `turn_complete` or `interrupted` it stores the user and assistant turns through `conversation.add_turn`. The client receives `{"type":"reconnect"}` on `go_away` and reconnects.

## Client (`frontend/lib/live.ts`, `components/Chat.tsx`)

- Auto-reconnect: an unexpected socket close (not user-ended, not an error frame) reconnects up to 3 times with backoff while keeping the microphone and playback contexts; the orb shows "Reconnecting".
- Tool calls show the orb in the thinking state until the voice starts.
- The worklet downsamples with a box filter instead of raw decimation, which reduces aliasing noise in the transcription.

## Tests

- `test_conversation.py`: order, limit, owner key across sessions, shopper isolation, bounded history text, blank turns ignored.
- `test_agent_runtime.py`: instruction provider appends history; empty history leaves the prompt unchanged.
- `test_live.py`: config carries the voice, VAD, resumption and compression; `TurnRecorder` saves turns on completion and on interruption; resumption handle stored and reused.
- Live: seed a conversation in Firestore, open the live socket, say "add it to my cart" with no product named, expect `add_to_cart` for the product from history.

## Rulings

- Firestore turns replace ADK's in-memory session as the memory of record. Cost: one small read per turn. Benefit: one memory for text, voice and restarts.
- Shopper memory is visit-scoped by design (anonymous); owner memory is account-scoped.
- No transcript is stored for the exit kiosk or for audio bytes; only text turns.

## Findings during implementation

- Live run 17 Oct: "add it to my cart" after a typed turn that named the rice resolved the right product from memory; the spoken answer to "where is atta" carried the aisle, and the map now highlights deterministically from the search result in store mode.
- The Live model sometimes skips a follow-up tool call (navigate_to) and sometimes invents a product id from a name in memory. Both are now handled in code: in-store searches emit a map highlight, and `add_to_cart` resolves an unknown id as a catalog name search (`resolved_from` in the result). Prompts alone were not reliable enough.
- Typed frames on the live socket carry no input transcription; the bridge records them itself so memory is complete.
