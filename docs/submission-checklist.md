# Submission checklist (Hack2skill portal, deadline 18 Oct 2026)

Links to submit
- Live app: https://royastacxk-aibuildercup.web.app (owner dashboard at /owner/, kiosk at /kiosk/)
- API: https://retail-api-881917398995.asia-south1.run.app (OpenAPI at /docs)
- GitHub: https://github.com/DSsathish/royalstack_aibuilderhackathon (must be public: `gh repo edit DSsathish/royalstack_aibuilderhackathon --visibility public --accept-visibility-change-consequences`, then open it in a logged-out window)
- Demo video: record with docs/demo-script.md, upload unlisted to YouTube, check in incognito that it plays
- Deck: export the slides artifact to PDF and upload

Before pressing submit
- [ ] Repo public, README renders, no secrets (`git log -p | grep -i "api_key\|secret" | grep -v "secret_for\|Secret Manager"` returns nothing sensitive)
- [ ] Live app opened in incognito on a phone: entrance QR works, voice works on Chrome, checkout works in sandbox
- [ ] Owner sign-in works with the registered Google account; a second Google account can register its own store
- [ ] Demo data fresh: `infra/scripts/reset_demo.py` if the demo store looks messy; forecast job run today
- [ ] Video under 3 minutes, link tested logged out
- [ ] Deck PDF under the portal size limit
- [ ] Theme: Retail & Commerce; team details match registration
- [ ] Submitted with at least three hours of buffer

Day-of operations
- Cloud Run keeps one warm instance (`--min-instances 1`); the first voice session after a deploy takes a few seconds longer.
- Scheduled jobs: forecast nightly 20:30 IST (every store), customers nightly 21:15 IST (segments, points expiry, stale holds), sync every 15 minutes (feeds and outbox).
- Phone sign-in uses Firebase test numbers +91 99999 00001/2/3 with code 123456; real numbers also work within the Spark plan's daily SMS allowance.
