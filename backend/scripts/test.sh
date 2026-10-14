#!/usr/bin/env bash
# Run the backend tests against a throwaway Firestore emulator.
set -euo pipefail
cd "$(dirname "$0")/../.."
firebase emulators:exec --only firestore --project demo-test \
  "cd backend && .venv/bin/python -m pytest -q $*"
