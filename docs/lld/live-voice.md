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

`WS /agent/live?session_id=<hex>` — validates the session (an unknown session is refused before accept, which the browser sees as a failed handshake), then `live.run`. One live socket per session; 15 minute maximum; audio frames over 32 KB are dropped. Owner mode allowed in dev/test only, as for `/sessions`.

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

## Review fixes (fresh-eyes review)

- Audio contexts are created synchronously inside the tap and resumed after the permission prompt, so iOS Safari does not leave them suspended.
- "Talk live" cannot be double-tapped into two sessions; a socket refused during connect does not leave a dead stop handle.
- Server limits: one live socket per session, 15 minute maximum, audio frames over 32 KB dropped, malformed text frames ignored.
- Real failures in the bridge now reach the client as an error frame instead of a silent close.
- Audio captured before the model is ready is dropped. The live button renders only after hydration.


## Addendum 18 Oct: live model through the Gemini API
- Vertex AI offers no live model beyond `gemini-live-2.5-flash` (and a native-audio variant in us-central1); AI Studio has `gemini-3.8-live`. The bridge therefore takes an optional `GEMINI_LIVE_API_KEY`: when set, `gemini.live_client()` is an AI Studio client (explicitly `vertexai=False`, because the SDK otherwise obeys `GOOGLE_GENAI_USE_VERTEXAI` from the environment) and `GEMINI_LIVE_MODEL` names the AI Studio model. Text, vision and embeddings stay on Vertex.
- `gemini-3.8-live` rejects `enable_affective_dialog`; `GEMINI_LIVE_AFFECTIVE=false` leaves it out. Everything else in the session config (voice, transcription, turn detection, compression, resumption, tools) works unchanged, and the three live scenarios pass on it.

- Reverted 18 Oct to `gemini-live-2.5-flash` on Vertex at the owner's request; the AI Studio path stays available behind `GEMINI_LIVE_API_KEY`.


## Addendum 18 Oct: echo, interruptions and transcript language
Field report: on a phone loudspeaker the assistant interrupted itself after its first reply, and the shopper's bubbles
showed the assistant's own words and `{background}`. Cause: the mic hears the loudspeaker; the browser's echo canceller
leaves a residue that the server-side turn detector takes for speech, so every reply became the next "question". Tamil
speech was transcribed in Devanagari because the input transcription had no language hint. Measured on the live model:
hint `ta-IN` fixes Tamil and leaves English and Hindi speech intact; a three-code hint that includes `hi-IN` tips Tamil
into Devanagari; the output `language_code` does not affect the transcript at all.

Browser (`lib/live.ts`, `lib/echoGuard.ts`)
- One AudioContext for both directions. Playback goes through a MediaStreamDestination into an `<audio>` element, created
  and started inside the tap, which is the output path browser echo cancellers track; falls back to the plain destination
  if media playback is refused.
- Jitter buffer: a reply starts 150 ms ahead, chunks append to the play head, a late chunk restarts with the same margin.
- EchoGuard, a pure class with unit tests. Per 100 ms mic chunk it gets the mic level, the loudest playback level of the
  last 350 ms, and whether playback (plus a 300 ms tail) is active. In the 150 to 650 ms window of each reply it measures
  mic against playback: mic under 0.012 means no echo path ("duplex", headphones: talk over freely); otherwise "speaker"
  with gain = mic / playback, and a chunk passes only when louder than 2.5 x the expected echo and 0.02 absolute. Held
  chunks are sent as silence so the model's timeline stays continuous; one chunk of look-ahead keeps word onsets (100 ms
  uplink delay). The mode drives the caption ("Speaking. Tap to interrupt").
- Tap to interrupt: flushes playback and discards the rest of that reply (audio and transcript) until the next
  `interrupted` or `turn_complete`; the shopper's speech then interrupts the model server-side as before.

Bridge (`agent/live.py`)
- Transcriber sound markers such as `{background}` and `<noise>` are removed; empty results are neither shown nor saved.
- Echo detection by text: a user transcript of three or more words that matches one of the last three assistant texts,
  either from the start (same first word, near-identical after dropping spaces and symbols, since the transcriber writes
  "5 kg" and "Rs 265" where the reply said "5kg" and "265 rupees") or as a long stretch (30+ characters, 85% covered) from
  anywhere in it, because the browser guard holds the first part of every reply so a leak starts later. A shopper repeating
  a short product name or rephrasing a command ("Add" after "Added") does not match.
- Echo detection by timing: a reply interrupted within 1.5 s of its first audio, twice in a row, is echo whatever the
  transcriber made of it (`CutCounter`); a completed reply resets the count.
- On either signal the client gets `{"type":"echo"}` once, the rest of that turn is not shown, and neither the echo nor the
  reply to it is saved. The client switches the guard to speaker mode, which is sticky for the session (a later quiet
  measurement never turns it back into headphones), and relabels the bubble "(echo from the speaker)". Detections are
  logged with the session prefix only.
- A line under the orb shows the guard's verdict: "Checking for speaker echo", "Headphones: talk over any time",
  "Loudspeaker: tap the orb to interrupt".
- Hosting serves pages with `Cache-Control: no-cache` (scripts stay immutable), so a deploy reaches phones on the next
  load instead of up to an hour later; the first field test of this work ran on the cached old client.
- Guest-session memory polluted by the loop (373 turns) was cleared; junk history had primed later replies
  ("I'm having trouble understanding you, please speak English").
- Replies cut by an interruption are saved with " [interrupted]".
- Language: `?language=` on the websocket (validated `auto|en|ta|hi`) sets the session language for the connection; the
  prompt gets "The shopper chose Tamil ..."; the input transcription gets `language_codes`: the chosen language alone, or
  in auto mode the store's regional language plus English (`["ta-IN", "en-IN"]` for the demo stores). Changing the
  language in the app restarts the live session.
- Verified with unit tests (clean, is_echo, recorder, config), the EchoGuard tests, the live scenarios, and two scripts
  against the deployed API: the spoken reply fed back as mic input produces an `echo` frame; the Tamil clip is shown in
  Tamil script.

Not done: no server-side echo cancellation; the guard holds the mic for the first 650 ms of every reply until it has
measured a headphone setup; on a loudspeaker the shopper interrupts by tapping, not by talking over.


## Addendum 18 Oct: languages
The model understands and speaks far more than three languages; the limits were ours. One table, `app/domain/languages.py`
(mirrored in `lib/languages.ts`), now drives the selector in the chat header, the profile and the store setup, the request
validation pattern (`CODE_PATTERN`), the prompt line "The shopper chose Telugu ...", the push-to-talk transcription hint, and
the live transcription hints. Each BCP-47 tag was checked against the live model: nine Indian languages plus Arabic,
German, Spanish, French, Indonesian, Italian, Japanese, Korean, Dutch, Polish, Portuguese, Russian, Thai, Turkish,
Vietnamese and Mandarin (`cmn-CN`; `zh-CN` is refused). Punjabi, Urdu and Odia are refused by the model and left out.
"Auto" remains the default: the prompt says to reply in whatever language the shopper uses, and the transcript hint is the
store's first regional language plus English. The read-aloud voice for text replies is picked from the script of the text.
A deliberate "End conversation" now also drops the session's resumption handle, so the next conversation starts with a
fresh model context (the saved transcript memory still carries over); reconnects after a network drop still resume.


## Addendum 18 Oct: spoken turns as voice notes
Decided with the owner: a spoken user turn shows as a playable voice note, in the shopper and the owner assistant; the
assistant's replies are unchanged. Audio stays in the browser; the text transcript is still what memory keeps.
- `lib/voiceClip.ts`: `ClipBuffer` collects the PCM chunks actually sent to the model (chunks the echo guard replaced with
  silence are never recorded), and `cut()` trims silence (RMS 0.012, two chunks of padding), drops turns with fewer than three
  loud chunks, and writes a 16 kHz WAV with 28 waveform peaks. Capped at 30 s per turn.
- `lib/live.ts`: a user transcript opens a turn; the first reply audio, the assistant transcript, a tool status or
  turn_complete cuts it and reports the clip (`onUserAudio`). An `echo` frame discards the buffer.
- While a voice note plays during a live session, the uplink sends silence (`notePlaying`), so the model never hears the
  shopper's replayed voice; one note plays at a time.
- Push-to-talk reuses the recording it already makes; the waveform is decoded in the browser.
- `components/VoiceNote.tsx`: play/pause, waveform with progress, duration, and "Show text" for the transcript. A turn with
  nothing loud enough to clip falls back to the text bubble at turn_complete; echo turns stay as "(echo from the speaker)".
- Clips are object URLs: they disappear when the page closes and are never uploaded.
