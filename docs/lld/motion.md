# Motion (18 Oct)

Motion answers a moment (arriving, waiting, an empty screen, a success) and never decorates a list. Animations come
from LottieFiles through its MCP server, downloaded into `frontend/public/motion/` so the app depends on no third-party
host at runtime.

## Where
- Landing page hero: one animation in place of the static store icon.
- Online shop while the home loads; "nothing matched" after a search; empty cart; order placed on the checkout page.
- Nowhere else: product cards, tables, the thread, the voice control (its canvas orb is already the live signal).

## How it stays cheap (`components/Lottie.tsx`, `lib/motion.ts`)
- The player (`@lottiefiles/dotlottie-react`, WASM renderer) is loaded with `next/dynamic` only by the screens that show
  an animation; the main bundle and every other page stay as they are.
- Each slot has a fixed box (no layout shift) and a static fallback (the icon that was there before) shown until the
  player is ready, when the file is missing, and always under `prefers-reduced-motion: reduce`.
- Plays only while visible (IntersectionObserver) and while the tab is visible; stops otherwise.
- Budget: one animation per screen, under 80 KB per `.lottie` file, no autoplay on more than one slot at a time.
- `lib/motion.ts` is the single registry: slot → file and fallback. An empty `src` means the fallback, so the UI is
  unchanged until an animation is chosen.

## Picking the files
Through the LottieFiles MCP: search by moment ("grocery bag", "empty cart", "searching", "order confirmed"), prefer
free, simple, few-layer animations that read in the app's green palette, download the `.lottie` into
`frontend/public/motion/<slot>.lottie`, and set the slot's `src` in `lib/motion.ts`.
