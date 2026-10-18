# Compact voice control (18 Oct)

Field report: on a phone the centred orb and its captions took a third of the assistant screen, so products, offers and
the thread were pushed under the fold while the assistant was active; the map tab could not be used mid-conversation.

## Layout
- The orb stage is gone from the chat screen. The thread starts right under the header.
- Shopper: the bottom bar gets a "Talk" slot between Scan and Cart (`components/VoiceDock.tsx`, variant `nav`): a 44 px
  mic button when idle, the live orb (mic level while listening, voice level while speaking, spinning arc while a tool
  runs) during a conversation. It sits inside the bar's safe-area padding and never covers content. It is on every tab,
  so the aisle map can be read while the assistant speaks.
- While a conversation runs, a status strip (`components/VoiceStrip.tsx`) sits in the page flow above the receipt bar:
  one line of status, one of the headphones/loudspeaker verdict, Interrupt (while speaking), End, Hide. It takes its own
  height, so nothing is overlaid: the thread and the map stay fully visible and scroll on their own.
- Hidden strip: the orb in the bar keeps showing the state. Tap it to bring the strip back.
- Owner assistant: the same control sits at the right of the header (variant `header`) with the strip under the header.
- The map tab scrolls on its own (`overflow-y-auto`), so a tall floor map is never clipped.
- Browsers without live audio (no AudioWorklet): the bar shows no Talk slot; the composer keeps its mic for push-to-talk,
  and the strip shows while that loop runs.

## Taps (`lib/voiceText.ts::dockAction`)
- No conversation: tap starts live voice on the current session (the owner's dock mints a fresh owner session first).
- Speaking: tap interrupts, as before (loudspeaker users rely on it).
- Listening, checking, connecting: tap shows or hides the strip. End is on the strip.

## Where the session lives (`lib/voiceSession.ts`)
The live connection, its frame handling (transcripts, voice-note clips, tool results through `lib/actions.ts`), the
echo-guard verdict and the levels moved out of `components/Chat.tsx` into one controller with a small zustand store
(`useVoice`: live, orb, level, guard, expanded, fallback, supported). The chat component only reads `live` to hide the
fallback mic and routes typed lines into the conversation with `voice.sendText`. A language change restarts the
conversation from the controller. The conversation ends with the screen that shows its control: the shop page on
unmount, the owner chat on unmount, and whenever the session changes.

## Tests
`lib/__tests__/voiceText.test.ts`: the tap mapping and the strip wording. Type check, lint and the static build cover
the rest.
