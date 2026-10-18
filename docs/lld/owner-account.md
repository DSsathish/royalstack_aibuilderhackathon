# Owner account settings (18 Oct)

An "Account" tab in the owner dashboard for the person's own sign-in. Store details stay under Store settings.

## What the tab offers
- Signed in as: the email, the method (Google account, or email and password), the verified mark, Sign out.
- Change email (email-and-password accounts): new email + current password. Firebase sends a link to the new address and
  the switch happens only when that link is opened, so a typo cannot lock the owner out and nobody can move the account
  to an address they do not control. The old address keeps working until then; Firebase signs the session out after the switch.
  Google accounts: the email is managed in Google; the tab says so.
- Change password (email-and-password accounts): current, new, repeat. The current password re-authenticates first.
  Forgot it: the existing reset link.
- Add a password (Google accounts): new, repeat. Google confirms the person first (popup), then the password credential is
  linked, so the same account also signs in by email and password.

## Where the logic lives
- `frontend/lib/firebase.ts`: `reauthenticate` (password credential, or the Google popup), `changeEmail` (verifyBeforeUpdateEmail),
  `changePassword` (updatePassword), `addPassword` (linkWithCredential). The API never receives a password.
- `frontend/app/owner/page.tsx::AccountTab`: the three cards, validation through the shared `guard`/`rules`, errors through
  `accountMessage` (wrong current password, re-authentication needed, popup blocked) falling back to the sign-in wording.
- `backend/app/services/auth.py::_follow_email_change`: ownership and staff roles are keyed by user id and never move.
  When a verified token arrives with a different address from the user record, the record is updated and the old address is
  swapped for the new one in each store's owner or staff list, with an audit entry per store. No endpoint, nothing to call:
  the next request after the switch does it.

## Not offered
Deleting an owner account: a store needs an owner. Shoppers keep their export/delete flow under the shopper profile.

## Tests
`tests/test_account.py`: an owner's new address replaces the old one in the store's owner list and the user record, a staff
member's new address replaces theirs in the staff list, both audited, and access continues throughout.
