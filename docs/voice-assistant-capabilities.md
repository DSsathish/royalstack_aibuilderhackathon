# What the customer voice assistant can do (18 Oct 2026)

Where: the shopper app on a phone, in store (after the entrance QR) or online. Tap the microphone; talk. Everything
below also works by typing, and the screen always shows what the assistant found.

## Starting and controlling a conversation
| Ability | How |
|---|---|
| Start, stop | Tap Talk; End conversation. Live speech-to-speech on Gemini Live, no app install. |
| Interrupt | Headphones: just talk over it. Loudspeaker: tap the orb (the line under the orb says which it detected). |
| Languages | Speak any language the model speaks; the selector offers 25 (Tamil, Hindi, Telugu, Kannada, Malayalam, Marathi, Bengali, Gujarati, English and 16 more). Auto follows whatever you speak; a picked language wins. Transcripts stay in the spoken script. |
| Reconnect | A dropped connection resumes the same conversation; the mic stays open across the gap. |
| Memory | Guests: this visit. Signed-in shoppers (phone OTP): earlier visits in this store, favourites, usual items, dietary notes, points. |
| Your own words | Each spoken turn shows as a playable voice note (kept on the phone only), with "Show text". |
| Fallback | Where live audio is unsupported, press-to-talk records, transcribes and reads the reply aloud. |

## What you can ask for
| Ask | What happens | On screen |
|---|---|---|
| "Do you have atta?", "Price of Aavin milk", "Basmati rice 5 kg" | Searches the live catalog; answers stock, price, sizes, pack maths ("10 kg" = two 5 kg packs) | Product cards |
| "What do you sell?", "Which sections do you have?", "How many products?", "What is out of stock?" | Knows the whole shop: every section and subsection with in-stock and out-of-stock counts, in its prompt and as a table on request | Sections table |
| "Give me the full list of vegetables in stock", "What dals are there?", "What is out of stock in dairy?", "next ten" | Lists a whole section in any language, in stock, out of stock or all, page by page; says the count, reads ten names, offers to continue | The full list as a table |
| "Is X out of stock? What else?" | Says out of stock plainly and offers in-stock alternatives (same subcategory, then category) | Alternatives as cards |
| "Where is toned milk?" (in store) | Finds it and lights the aisle and bay on the map; aisle QRs update where you stand | Map highlight |
| "What is A2 milk?", "Ingredients of this atta", "Does it contain gluten?" | Looks it up in public sources with citations; label data from Open Food Facts for real barcodes; refuses off-topic lookups | Facts card with sources and the disclaimer |
| "Any offers today?", "How many points do I have?" | Offers that apply to you (segment-aware) and your points balance | Offers strip |
| "Add two packs of atta", "Remove the milk", "What's in my cart?" (online) | Updates the cart; in store, items enter by scanning only | Cart and receipt |
| "Checkout", "I want to pay" | Starts checkout; points can be spent after a fresh OTP | Checkout screen |
| "I'm looking for X" and it is not carried | Says so honestly and records a demand signal for the owner | Signal recorded |
| A photo ("What is this?") | Identifies the product in the photo and searches for it | Matching cards |

## Guarantees
- Stock, prices and locations come only from tool results, never from memory; the screen renders tool results only.
- Discounts, points and totals are computed in code inside transactions.
- Off-topic requests are brought back to shopping; product facts are limited to product topics with citations.
- Nothing about you is sent to the web; voice notes never leave the phone; signed-in shoppers can export or delete everything.

## Not supported yet
- Home delivery or order tracking (online mode is cart and payment only).
- Returns, invoices, and talking to a human.
- Product facts for items without any public information (it says so instead of guessing).

## Accessibility
- Voice-first with full text equivalence; large tap targets; visible focus; reduced-motion respected.
- Controls carry screen-reader labels (orb, play buttons, form errors announced as alerts).
- Light and dark themes follow the phone; transcripts in the shopper's own script with Tamil and Devanagari fonts.
