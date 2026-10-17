# Shopper assistant screen and shell (18 Oct)

Field report: on a phone the voice orb stage took a third of the screen, "End conversation" was a separate button, and
nothing showed when the agent was searching the catalog or looking something up.

## Design plan
- **Subject and job**: a shop assistant used one-handed while walking the aisles, often on a loudspeaker, in Tamil,
  Hindi or English. The thread is the page; the receipt stays in view; one control talks.
- **Tokens**: unchanged shopper palette (near-white green base, forest ink, one leaf accent, amber only for warnings;
  the dark scheme mirrors it). Type: Bricolage Grotesque for the store name, Figtree for everything else, JetBrains Mono
  for money. No new colours.
- **Layout**: compact header (store name, tagline in sentence case, sign-in chip, language, read-aloud toggle); the
  thread fills the rest; a floating voice pill sits bottom-right above the composer within thumb reach; composer with
  camera and send only; receipt strip; bottom nav.
- **The one memorable element**: the pill's ring. It shows the mic level while listening and the assistant's voice while
  speaking, spins dashed while a tool runs (the label names the tool: "Checking the shelves", "Looking up facts"), and
  fills red while a long press ends the conversation.
- **Review against defaults**: no orb stage, no all-caps eyebrow in the header (the tagline is sentence case), no new
  card kit, no decorative motion; the only animation answers audio or a tool.

## Behaviour (`components/VoicePill.tsx`, `lib/voicePill.ts`, `components/Chat.tsx`)
- Idle: a 48 px round mic button. Tap starts live voice (or the push-to-talk fallback where live audio is unsupported).
- Connecting / reconnecting: dashed spinning ring, "Connecting" / "Reconnecting · Keep talking".
- Listening: ring follows the mic; second line is the echo-guard verdict, "Headphones · talk over any time" or
  "Loudspeaker". Tap ends the conversation, unless the assistant stopped speaking under 800 ms ago, in which case the
  tap is taken as a late interruption and ignored (`tapAction`).
- Tool running: label is the tool in plain words, ring spins dashed. Also shown in text mode while a reply is produced.
- Speaking: ring follows the assistant's voice; "Tap to interrupt" (loudspeaker) or "Talk over or tap to interrupt"
  (headphones). Tap interrupts (live) or stops the read-aloud (text mode).
- Long press (600 ms) ends from any live state, with a short vibration where supported; the hold ring shows progress.
- Reduced motion: the spin and hold animations are off; levels still show.
- Owner assistant shares the component and inherits the owner theme tokens.

## Tests
`lib/__tests__/voicePill.test.ts` covers the tap mapping and the pill text. Type check, lint and the static build cover
the rest; the kiosk page does not use the removed orb.
