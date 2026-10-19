# Demo video (2 min 27 s)

Rendered by `infra/scripts/demo_video/` tooling notes below: headless Chrome drives the live site (Playwright), each scene is fitted to its narration, captions are drawn, the voice is Google Cloud Text-to-Speech `en-IN-Chirp3-HD-Kore`, ffmpeg composes a 1920x1080 MP4. The file is not versioned; it is uploaded to Google Drive and linked from the deck.

## Scenes and narration

1. **Royal Stack** (One AI commerce agent. One inventory truth.)  
   "Every small shop already runs on billing software. But shoppers get no help in the aisle, and owners guess their reorders. Royal Stack is one AI commerce agent and one inventory truth, built on Google Cloud."
2. **Two front doors** (Store visit from the entrance code. Shop online from anywhere.)  
   "Two front doors. The store visit starts with the entrance code. Shop online opens a product-first home: live deals, what shoppers bought most this month, and picks for returning customers."
3. **In the shop** (Scan the entrance code. Ask, and the map shows the shelf.)  
   "In the shop, the visit starts with the entrance code on the phone's camera. Ask where something is, in your own language, and the assistant answers, highlights the shelf on the map, and gives directions by department, bay and shelf. Items enter the cart by scanning, so the exit check has something to verify."
4. **Search that knows the shelves** (Sections, departments, label facts and price comparison.)  
   "Search understands sections. Healthy food lists exactly that section. Every product carries its department and shelf. The product sheet looks up label facts from public sources with citations, and compares prices across connected providers. Sample rows are clearly marked as demo data."
5. **The assistant** (ADK agents on Gemini, tools over the live catalog, 25 languages.)  
   "The assistant is the same in store and online: Google ADK agents on Gemini, with tools over the live catalog. Ask where something is, what it costs, or for a full list of a section, by voice in twenty-five languages, or by typing."
6. **Cart and checkout** (Offers apply themselves. The receipt carries the exit code.)  
   "Offers apply themselves in the cart, the best one per item and one per bill. Checkout is a tap, and the receipt carries the exit code the kiosk verifies."
7. **The owner's dashboard** (Today's sales, forecasts with days of cover, reorder drafts by supplier.)  
   "The owner sees today's sales, stock that needs attention, and BigQuery ML forecasts with days of cover for every product. Reorder drafts arrive grouped by supplier with a written rationale, and nothing is sent until the owner approves."
8. **Demand and customers** (What shoppers asked for. Segments that offers can target.)  
   "Demand signals record what shoppers asked for and could not get, in any language. Customers fall into segments, new, regular, VIP and at risk, and offers can target them."
9. **Inventory integrations** (Files, sheets, APIs, databases, MCP servers. Preview, then confirm.)  
   "Inventory comes in from files, sheets, APIs, databases, or any MCP server. The connector agent proposes the mapping, previews the change, and writes only after confirmation. The shop's own catalog is served as an MCP server too, so other agents can shop it."
10. **Built on Google Cloud** (Firebase Hosting · Cloud Run · ADK · Gemini Live · Firestore · BigQuery ML · Vertex AI · Secret Manager)  
   "Firebase Hosting, Cloud Run with Google ADK and the Gemini Live bridge, Firestore, BigQuery ML, Vertex AI, Cloud Scheduler and Secret Manager. Three hundred and eighty tests behind it. Royal Stack."

## How it was made
- Scenes 2 to 9 are recordings of https://royastacxk-aibuildercup.web.app in headless Chrome: phone viewport for the shopper (the store visit starts from the signed entrance link in docs/entrance-qr.png), 1440x900 for the owner (a throwaway owner account, removed afterwards).
- Scenes 1 and 9 are brand cards.
- Long recordings play faster to fit the narration; short ones hold the last frame.
- Tooling lives in the session's scratch folder (record.mjs, compose.py, script.json); the narration above is the source of truth if it is re-rendered.
